# P02 model and numerical decision records

Status: **INTERNALLY REVIEWED PROPOSALS — NOT APPROVED OR IMPLEMENTED**. CAN-01 remains open. No project is migrated; no numeric output is changed. Founder product clarification is in `EXECUTION_SCOPE_AND_PRODUCT_RULES.md`.

Application source is unchanged from `ab7db888e85fb9b6125551ecff769d08e0ca7322`; P01 additions are at `ef22d42c4647e15cd0d6815b9d3816702cf9dbb4`. The evidence manifest fingerprints inspected files. File/function references below identify current code, not proof that the proposed behavior is implemented universally.

## ADR-01 — Authority and projection ownership

**Problem:** design data has several valid representations; uncoordinated writes can make them disagree. Rewriting all representations into one mutable object would risk existing data and does not itself prove consistency.

| Concern | Proposed authority | Current evidence / required adapter invariant |
|---|---|---|
| Editable geometry and stable IDs | `civora_object_v1` records within `canonical_project_v1` | `site_objects.object_definition/placement_from_definition`; `canonical_canvas.with_canvas_snapshot/resolve_canvas_input`; preserve wrapper-only unknown data, IDs/order and explicit object geometry precedence |
| Versioned aggregate | `civora_project_v1` document at existing persistence boundary | `canonical_project.validate_project_document`; strict known version/section shape and finite JSON; allowed extensions retained |
| UI rendering/edit projection | `BuildingPlacement` and canvas workspace adapter | `apps/web/app/utils/canonicalCanvasProject.ts`; snapshot at serialized save boundary, no competing React engineering store; runtime cross-language parity still requires later testing |
| Legacy planner inputs | `ProjectInput.manual_fields`, controls and metadata are explicit compatibility projections | `canonical_record.with_model_snapshot/resolve_model_input`; full canvas snapshots differ from legacy program-only inputs; do not invent placed geometry for sparse program descriptors |
| Source basis and requirements | Canonical `site.site_inputs_v1` plus referenced source/assumption records | `canonical_record.seal_record/project_view`; incoming canonical basis wins over stale legacy shadows; accepted/imported does not mean verified |
| Units/CRS/datum | Explicit project/site and per-source/per-surface metadata | Project `units`/`coordinate_system` currently exist, but complete surface registration is missing; unknown remains unknown, never guessed feet |
| Computation geometry | Derived `ProjectModel` (`core/geometry_core.py`) | Rebuild from exact immutable input identity; no independent persistent owner of editable source geometry |
| Stage metrics/dependencies/checkpoints | Job-scoped `ProjectManager` (`core/project_manager.py`) | Execution state, not editable source; checkpoint separation belongs to P16 |
| Results and result facets | Immutable calculation record plus exact source/method identity; active pointer conditional | `canonical_record.FACETS`, `result_from_document`, `seal_record`; current active sidecar + canonical facets are explicit split storage; detach/hydrate through `portable_document` |
| `final_plan.actions` / quantities / costs | Derived views of a bound result, never a second editable design | Generated geometry is not automatically user-accepted geometry; adoption must be an attributable edit; correct calculations still need independent validation |
| Edit vs calculation history | Separate preserved histories | `edit_transactions.seal_edit_history`; canonical history references and `project_store` calculation records; no retroactive overwriting or inferred approval |
| Export | Immutable snapshot of explicit geometry-only or calculated scope | Artifact workflows must bind input/result/revision and recheck freshness/role; P20/P34 prove connected external compatibility |
| Reviews | Attributable records bound to exact input/result/artifact | Software source acceptance, professional review and engineering validity are separate statuses; Civora does not sign/seal |

**Decision proposal:** retain v1 + explicit gateways; make ownership/write-set contracts testable. Do not introduce schema v2 or a new universal kernel in P02. **Alternative:** replacing all models with one schema now is rejected for lack of demonstrated necessity and migration risk.

**Acceptance before implementation:** architect/data-integrity owner reviews every arrow; preserve old readers/IDs/source/history/unknown extension data in selected fixtures; make all writers revision-safe in P09. P02 pure roundtrips cannot prove DB transactions or full UI parity. Rollback is documentation/test-only; future migrations need their own recovery decision.

## ADR-02 — Invalid inputs, failures and meaningful zero

**Current issue:** hydrology can report success for negative/nonfinite inputs and the planner can turn a missing result field into zero. P02 does not repair either.

**Recommended internal contract:** typed `EngineeringInputError` and `EngineeringComputationError` with stable code, field and safe explanation. API/job adapters translate them into structured failures; existing wire shapes remain readable through explicit versioned adapters. Missing contract fields, nonfinite intermediate/final values, unsupported domains and nonconvergence cannot activate a successful engineering result. A catch-all fallback must not invent a replacement answer.

**Alternative:** structured result objects throughout every engine can work if every consumer checks them before using values. Do not mix error conventions accidentally. Typed errors are a recommendation pending backend/engineering review, not newly implemented classes or response codes.

- Reject booleans as physical numbers, missing required inputs, negative area/intensity, nominal C outside `[0,1]`, NaN and infinities.
- Distinguish valid explicit zero from missing/no-catchment data. Proposed explicit area/C/intensity zero can yield numerical zero within a documented supported domain; an empty list is a no-data/no-catchments outcome, not verification of zero site runoff. Final policy needs domain review.
- Rainfall/Tc heuristics remain estimated. A finite number is not a sourced design storm. No universal maximum rainfall/site-size limit is invented here.
- Result `success` describes computation in a supported domain, not professional approval. Status/provenance/staleness/review are orthogonal.
- Preserve original old results as old-method/unverified records; no silent re-labeling after a repair.

**Future acceptance:** P03's invalid/zero/missing/unit/adapter/job tests with independent expected values; legacy readers and error mapping reviewed. Side effect: valid-looking old inputs may now fail instead of producing numbers; provide actionable errors, not relaxed validation. Review owner: backend/numerical lead; discipline review for supported physical scope. No approval recorded.

## ADR-03 — Surface sampling and integration

**Current evidence:** `GridSurface.x_at/y_at` and `SurfaceEngine.build_grid` / `TinSurface.build_grid` use nodes at `origin + index*spacing`; maxima reflect `(count-1)*spacing`. Earthwork/grading currently integrate each sample as a whole cell. Imported raster/legacy fixtures may have different semantics. Do not infer sampling solely from array shape or bounds.

**Proposal: separate explicit kinds, not one ambiguous array:**

1. **Node grid:** affine node coordinates, rows/columns count sample vertices, node domain spans adjacent cells. For 3×3 nodes at 10-ft spacing over `[0,20]²`, there are four 100-ft² cells; constant +1-ft difference gives 400 ft³. A single row/column has no 2D integration domain unless another documented representation supplies it.
2. **Cell-value/cell-centre raster:** pixel-corner affine transform defines support; dimensions count cells; centre sampling and represented quantity meaning are explicit. Correct cell area is the transform determinant, not necessarily scalar spacing squared. NoData stays masked, not zero elevation.
3. **TIN:** XYZ vertices and explicit indexed triangles with boundary/hole/breakline provenance. Degenerate/overlapping/missing coverage must be rejected or reported, not quietly filled.

**Proposed node-cell integrator to review:** deterministic piecewise-linear triangles on a documented fixed diagonal, clipped to the valid comparison boundary. Split triangles at cut/fill zero crossings, integrate positive/negative volumes separately and maintain signed-net conservation. A bilinear-cell method is a legitimate alternative but can differ on nonplanar data; choose and version one before P06 implementation. Do not switch methods based on which passes a fixture.

**Analytical review targets (not results from a repaired engine):** uniform +1 ft on 20×20 ft → fill400; `dz=x/20` → net200; `dz=x/10-1` → cut100/fill100/net0. Test clipped/partial cells, holes, resolution, NoData and TIN comparisons. Separate raw geometric volume from stripping and loose/compacted material factors; factor direction/order needs approved definitions.

**Legacy ambiguity:** a 2×2 sample array with spacing10 and stated bounds0..20 is inconsistent with the node convention. Preserve original representation and mark unclassified; never silently shrink its domain or multiply its volume by an arbitrary correction. Proven constructor/importer metadata may justify a classification; absence requires explicit confirmation. No migration occurs here.

**Review owners:** numerical/geospatial lead and qualified discipline reviewer. Interpolation, factors, clipping and supported scope remain unapproved. P05 registers surfaces before P06 integrates. Rollback must not reactivate known-wrong results.

## ADR-04 — Units, CRS, datum and resampling

**Proposal:** future versioned surface registration records horizontal CRS/axis order, XY and Z units, vertical datum, affine origin/basis vectors, extent, sample kind, NoData and provenance/method version. This is a metadata requirement, **not a new persisted schema introduced here**.

- Separate international foot, US survey foot and metres; require explicit conversion provenance. Drawing metre support does not establish metric correctness of every engine/export.
- Direct comparison requires compatible frame/units/datum/domain/orientation/sampling, not just equal shapes. The audited 1,000-ft shift must reject with field-specific reasons.
- Unknown registration blocks trustworthy comparison; still preserve/load a draft without inventing feet, datum or precision.
- Resampling/reprojection is an explicit, attributable operation producing a new surface ID and retaining the original. Record kernel, target grid, clipping/mask, transform and error budget. Never resample silently to make arrays align.
- Horizontal reprojection is not vertical-datum conversion. Unsupported datum transforms stay unsupported; P02 does not download grids, call GIS services or add dependencies.

**Alternatives:** rejecting all mismatches is safest initially; later explicit approved resampling can widen scope. **Acceptance:** P05 mismatch/positive-control cases plus independent geospatial reference points and transform provenance. Reviewer: geospatial/numerical specialist; discipline reviewer for physical accuracy. No approval recorded.

## ADR-05 — Methods, tolerances and reproducibility

Proposed authoritative hydrology result field remains `total_runoff_cfs`; no default-zero alias for missing data. Actual downstream caller verification belongs to P03. Basin/storage/routing method corrections belong to P04; P02 does not approve a catchment method, rainfall source, stage-discharge assumption or jurisdictional standard.

Each future benchmark must record expected value independently, units, source/method/version, absolute+relative tolerance and acceptance rule **before** inspecting repaired output. The P01 decimal tolerances are historical diagnostic precision, not universal physical/design accuracy. No fixed numerical tolerance is professionally approved in this package.

Required layered evidence: analytical arithmetic; conservation and boundary/domain tests; independent reference comparison with matched assumptions; connected input→result→save/reload→export trace; qualified method review for the advertised scope. End-user responsibility for final deliverables does not replace any software verification layer.

Result identity must include exact input/source/method/engine/config versions. Old results stay inspectable, stale/failed/unknown states do not become current by opening a project, and corrected calculations create new records. Formal supported-method and tolerance acceptance stays pending; method/standard documents are not fetched or assumed current here.

## ADR-06 — Revision and migration boundary (design only)

Preserve existing v1 wire/document names. Propose server-issued design CAS separated from scoped metadata/result revisions; all writers must participate (P09). Calculation completion may append an archived record but activates only against matching current input/method/permission. Do not carry captured stale inputs back over current geometry. Existing revision-aware snapshot wrapper is retained.

Migration phases: characterize → add explicit versioned readers/metadata only after approval → dry-run on synthetic/authorized copies → preserve original snapshots and compare counts/identity/provenance/history/results → dual-read with one controlled writer → explicit recomputation/review → separately approved contraction. No broad legacy bypass; ambiguous surfaces stay unverified. DB rollback, schema changes and production restore need separate authorization. P02's rollback removes only its new preparation files and retains evidence; it never rewrites saved projects.

## Decision/approval register

| Record | Internal preparation | Required substantive review | Formal approval |
|---|---|---|---|
| ADR-01 ownership | Prepared, contract-tested subset | Architect + data-integrity owner | PENDING |
| ADR-02 failure/zero contract | Recommendation only | Backend/numerical lead; discipline input for physical domains | PENDING |
| ADR-03 sample/integration semantics | Alternatives and oracles prepared | Numerical/geospatial + qualified civil-method reviewer | PENDING |
| ADR-04 registration/resampling | Metadata/comparison requirements prepared | Geospatial specialist + discipline reviewer | PENDING |
| ADR-05 supported methods/tolerances | Qualification rules only | Scope-specific method/benchmark reviewer | PENDING |
| ADR-06 revisions/migration | Compatibility strategy prepared | Architect + DB/security reviewer | PENDING |

No named reviewer, licensure or outside acceptance is fabricated. These documents enable precise review and later small authorized repairs; they do not replace it or authorize the rest of the backlog.
