# CIVORA ENGINEERING VALIDATION PLAN

Baseline: 2026-10-15, `ab7db888e85fb9b6125551ecff769d08e0ca7322`. PROPOSED; no new engine execution, numerical approval or PE acceptance in this task.

## 1. Claim-based qualification, not engine-name certification

Owners: engineering lead, independent discipline PE(s), geospatial/numerical specialist, QA oracle custodian. Linked issues ENG-01–06, CAN-02, TEST-02/03, EXP-01/03, AI-01. Packages P02–P06/P15/P18–P20/P34/P35. P18 is a parent qualification budget (75–150 engineer-days), split Q01–Q30 below into independently reviewable child scopes typically 2–8 days; approve exact child allowlist and avoid double-counting known-defect repairs in P03–P06. Newly found solver defects become new tickets/reserve, not presumed included fixes.

Each enabled claim needs: precise supported input/domain/units; governing method and edition/jurisdiction; independently authored expected values; source artifacts/rights/hashes; absolute and relative tolerances established BEFORE observing Civora; invalid/boundary/conservation cases; reproducibility manifest; connected UI/job/persistence/export trace; independent review/disposition. All Q records start **NOT TESTED / UNVERIFIED** here. A geometry generator can qualify geometry without claiming professional design adequacy. Unsupported claims must remain disabled or disclosed, not silently excluded from testing.

Candidate references below are acquisition/review targets, not downloaded/current-edition-verified authorities. Obtain official publisher versions, local amendments, license and reviewer acceptance before execution. No online retrieval or paid tool use authorized by this plan. Vendor-reference software is an independent comparison only when input assumptions/units/solver scope match and its own configuration is captured.

## 2. Proposed common numerical contract (ADR approval required)

- Internal engine inputs carry physical quantity meaning, units and provenance; convert at a single explicit boundary. Preserve original numeric value/unit/source. Distinguish international foot (0.3048 m) from US survey foot; no guessed vertical conversions.
- Reject bool-as-number, missing required values, NaN/Inf, malformed arrays and incompatible datum. Do not replace them with zero. Preserve legitimate zero flow/area/difference and explain no-data vs no-flow.
- Recommend typed internal `EngineeringInputError`/`EngineeringComputationError` (names proposed) with field/code/reason/source. API maps validation to structured 422; jobs/stages fail with actionable message and no active-success publication. Structured failure-result alternative must be decided consistently in ADR-02.
- `success` means valid execution in the documented domain, not PE acceptance; status separately records computed/estimated/unverified/stale/failed/reviewed. No partial successful subtotal masquerades as a complete site.
- Rational nominal C in [0,1], area/intensity >=0 and finite; empty areas return a documented no-catchments status, not “verified zero design”; zero-area row may yield valid zero if approved. Tc must have sourced method/domain/units and positive finite engineering basis. Design rainfall zero may be numerically valid but not accepted as a design storm without explicit context.
- No universal upper bound invented for rainfall, site size, grade or pressure; documented supported limits and jurisdiction checks govern. C/Tc/intensity heuristics remain estimated and cannot satisfy source-backed gates.
- Validate intermediate and final values. Underflow/overflow/nonconvergence and missing contract fields are failures, not exception fallbacks computing another silent formula.
- Preserve full calculation precision until presentation. Serialize finite values with roundtrip-capable precision; record display rounding independently. Store method/engine version, inputs/config/source hashes and tolerances. Same frozen inputs/environment must reproduce within declared deterministic tolerance; AI/provider context captured separately.
- Proposed analytical tolerance: abs <=1e-6 in the stated base output unit plus rel <=1e-9, evaluated as abs_error <= max(abs_tol,rel_tol*abs(reference)). This is an internal arithmetic proposal, not a universal survey/design accuracy claim. Physical/reference tolerances require PE approval per metric.
- Proposed routing checks: mass residual <=max(0.1 ft3,0.001*inflow volume), step-halving peak stage change <=0.01 ft and peak outflow <=1%, only within approved supported cases; time-zero/no-inflow denominator handled explicitly. Reviewer may require tighter/method-specific bounds before results. Do not loosen after observing failures.
- Geometry tolerance distinguishes computational coincidence, chord approximation, survey/control accuracy and legal setback. Parametric road 0.02-ft chord setting is an approximation budget, not design clearance.
- Earthwork conservation compares signed net, separate cut/fill, boundary-clipped domain and factor-adjusted quantities. Separate stripping, loose excavation, compacted fill, swell/shrink and topsoil inventory; factor names/definitions must be approved, not inferred.
- Every approval binds exact supported scope/revision; imported/AI/user accepted data is not automatically professionally verified.

## 3. ENG-01/02 repair design and caller inventory

Current `HydrologyResult.total_runoff_cfs` is defined at engines/hydrology_engine.py:18. `runtime._compute_hydrology_metrics`:958 requests total_flow_cfs with a default 0. Planner imports helper and calls at planner.py:9989; direct drainage Apply path imports/calls through job_workflows.py:1545/1670. StormNetworkResult separately uses total_runoff_cfs; not all same-named contracts should be mechanically renamed.

Plan: establish typed authoritative result, direct required field access and validation; missing result contract fails explicitly. If old serialized results use another key, versioned reader alias only with unambiguous schema provenance, never merge conflicting values. Trace result→stage→quantity/report/export, while recognizing inspected drainage/storm callers also take C/I directly. Prove which outputs use peak before stating risk magnitude. No proof all pipe sizes were zero.

Regression oracles:
- one acre, 50% impervious under existing helper's estimated C=.625, I=4: Q=2.52cfs. This validates adapter arithmetic only; does not approve estimated hydrology basis.
- 2ac,C=.8,I=4 gives 6.4512cfs; multi-area sum analytically independent.
- explicit zero C/I/area semantics, empty set, small positive and bounded large values.
- negative area/intensity, C outside [0,1], missing, strings/bools, NaN/±Inf; success must never accompany invalid output.
- unit equivalence using original-unit conversion and precision; no acres/square-feet mix.
- invalid Tc, unsourced storm/intensity and ambiguity cannot produce source-verified result.
- actual helper/job/planner integration, no mocks replacing HydrologyResult with another expected schema.
- old projects stay loadable; prior results retain old method and cannot be relabelled corrected without rerun.

## 4. ENG-03 basin/routing design

For a rectangular flat bottom with equal outward side slope s:
A(z)=(L+2sz)(W+2sz); V(d)=LWd+s(L+W)d²+(4/3)s²d³.
Use differences V(z2)-V(z1) for every stage interval, including terminal fractional increments. For other geometries, define a separate explicit method, not accidental frustum reuse. No geometry clamps hidden from result.

100x20x5ft at4H:1V: V=24666.666666667ft3. Original direct=24164.633843973; curve endpoint=24661.586710288. Square100x100 control=72666.666666667; positive rectangular mismatch and internal inconsistency share root cause. Cases: dry prism s=0 only if supported, 1:1/4:1, unequal L/W, zero depth, depth near increments, dimensions at supported bounds, rejected negative/bools/NaN, freeboard separate from wet storage.

Routing: state initial storage/stage; validate strictly increasing hydrograph times, monotone stage/storage and stage/discharge, outfall/tailwater assumptions, time units, coefficient and outlet geometry. Solve continuity within reviewed method; output integrated inflow/outflow/storage/residual. Zero outlet conserves storage; overflow either explicit reviewed spill path or return out_of_supported_range when volume exceeds curve. Never clamp displayed stage while accumulating unlimited unseen storage. No support claims for backwater/multiple outlets/unsteady pipe interaction unless separately benchmarked. Compare h/h2/h4 and an independent solver with same stage/discharge; PE approves hydrograph/rainfall/design-event/release assumptions.

## 5. ENG-04/05 surface/integration design

Existing SurfaceEngine constructors: bounds/(spacing)+1 nodes, x_at/y_at sample coordinates; Earthwork and Grading multiply each sampled point by cell_size². A 3x3 node mesh over[0,20]² has FOUR 10x10 cells, not nine. Correct uniform1ft volume400ft3. Existing2x2 fixture with bounds0..20 and spacing10 encodes inconsistent semantics and must be classified, not reused as an oracle.

ADR-03 defines:
- Node grid: nrows/ncols vertices, affine node coordinates, extent determined consistently by steps; integrator iterates spatial cells.
- Cell-centre raster/value grid: values represent cell support explicitly bounded by affine pixel corners; NoData mask; cell area from affine determinant, not always square.
- TIN: points/triangles, orientation/holes, boundary clipping and explicit breakline constraints.
- Interpolation choice (bilinear vs fixed triangulation) and cut/fill zero-crossings specified. Signed net can integrate exactly while separate positive/negative volumes need actual subdivision; do not simply sum signed corners.
- Existing/proposed surfaces compared over approved common domain. Reject disjoint/misaligned unknown-registration surfaces; never index-match by shape alone.
- Legacy metadata missing: preserve read-only draft, mark comparison unverified and require explicit operator/engineer classification. No in-place silent array re-interpretation.
- Optional resampling requires original preserved, declared kernel/grid/mask/transform, error budget and new derived-surface ID. Horizontal reprojection is not vertical-datum transformation; unsupported grids/datum conversions block.
- Cell dimensions may differ in x/y; rotated/sheared affine grids need correct area and alignment comparison. Units and axis order explicit.
- Compare grid refinement and independent TIN on plane/wedge cases; document nonplanar interpolation difference, not force equality beyond justified tolerance.

Test volumes: constant raises/lowers; plane dz=x/20 over20x20 has net200ft3; dz=x/10-1 over0..20 has net0, separate cut=fill100ft3. Clip to half rectangle and triangle/concave boundary with analytical integrals; holes remove area; partial cells preserve conservation. Null cells fail completeness or explicitly report incomplete domain, never zero-fill silently. Shift by1000ft, rotate, CRS/unit/datum/resolution mismatch -> field-specific incompatibility. Shrink/swell examples authored from approved material definitions; raw400 remains raw before separately labelled adjustments.

## 6. All-family qualification matrix

Every row inherits section2 input/domain/finite/unit/datum validation, source hashes, output lineage, independent expected author, code+connected regression, and PE/specialist acceptance. “Reference” is a candidate to acquire and verify, not already accepted. “Conservation” includes counts/topology/area where fluid/mass balance is inapplicable.

| Child / family / source modules | Supported claim and assumptions/reference to approve | Independent analytical and boundary cases | Units/datum/tolerance/conservation and regression/review | Explicit unsupported claims |
|---|---|---|---|---|
| Q01 Hydrology; hydrology_engine/runtime | Rational peak only in approved catchment/Tc/storm domain; local IDF and accepted drainage manual, FHWA/NRCS where applicable | P03 cases, composite runoff and zero/nonfinite, Tc method endpoints | ac/sf/ha,m/mm/hr/in/hr; Q/area sum; tests independent formula; hydrology PE | Unsourced rainfall, arbitrary watershed size, full hydrograph from peak |
| Q02 Detention; detention_engine | Declared storage geometry and approved continuity/outlet model; local detention manual, EPA SWMM reference with matched assumptions | P04 basins, constant/triangular hydrograph, zero outlet/dry/overflow/timestep | ft3/m3,cfs/time; monotone curves, residual/convergence; PE | Unqualified spillway/backwater/tailwater or emergency design |
| Q03 Surface/TIN; surface_engine | Interpolation of accepted survey/control, documented extrapolation; survey reference set and independently triangulated planar cases | Plane/tilted plane, collinear/duplicate points, breaklines, hull/outside/hole, huge coordinates | CRS/datum/XY/Z; plane exactness, topology, breakline preservation; geospatial+PE | Survey certification from public terrain; unbounded extrapolation |
| Q04 Contours; contour_engine/surface | Isolines of declared surface; independent GIS/reference mesh | Plane contours, saddle/plateau, exact vertex, noninteger interval, missing cells | Elevation levels/segments/closure and area; scale-aware geometry tolerance; PE/GIS | Hydraulic drainage adequacy from contour appearance |
| Q05 Grading; grading_engine | Declared element/surface blending and slopes; local grading/accessibility criteria | Constant/tilted pad, swale/crown, transition overlap, ties/boundary and zero influence | Slope ratio vs %, datum; shared earthwork engine parity, no extra material; PE | Automated optimal grading or ADA compliance without accepted criteria |
| Q06 Earthwork; earthwork_engine | Approved spatial-domain cut/fill and material accounting; independent integral/TIN/reference CAD | P06 planes/wedges/partial cells, signed crossings/nulls/strip factors/refinement | ft3/yd3/m3 and origin/datum; raw/factored balances; geospatial+PE | Unknown-grid/index-only comparisons or geotechnical factors guessed |
| Q07 Catchments; storm/catchment_engine | Declared contributing polygon/runoff allocation; independently delineated watersheds | Rectangle split, disconnected outlets, overlap/hole/flat terrain | Area sum/assigned runoff and nonduplicated allocation; PE | Universal watershed truth on coarse/unverified terrain |
| Q08 Inlets; storm/inlet_engine | Approved gutter/capture/bypass formula and inlet type; official FHWA HEC-22/local criteria | Triangular gutter analytic forward case plus independently expected inverse; sag/on-grade/bypass/blocked grate | cfs,ft,slope;n; Qcapture+Qbypass=Qapproach; PE | Inverting own function alone as correctness, all grate configurations |
| Q09 Storm topology; storm_network/basin_connection | Declared DAG/network graph and tie-ins; independently drawn network | Branch/merge/deadend/disconnected/duplicate/cycle/outfall constraints | Node/link identity and runoff connectivity conservation; PE | Every loop or unknown outfall automatically solved |
| Q10 Storm hydraulics; storm/hydraulic_engine | Specified Manning normal-flow and HGL/EGL method; official hydraulic references/approved HDS-5 or SWMM cases | Full/half flow circle, adverse/zero slope, surcharge, tailwater and long series | in/ft/m,cfs,m3s; head/energy/mass budgets; binary search residual; PE | General dynamic-wave/backwater/transient equivalence without proof |
| Q11 General pipe; pipe_engine | Declared capacity/layout calculation only; reconcile same method with storm | Duplicate independent pipe cases, empty/zero/diameter bounds/negative roughness | Same unit conversion and capacity invariants as Q10; PE | Geometry-only pipe presented as engineered hydraulics |
| Q12 Sanitary; sanitary_engine | Adopted fixture/flow/slope/capacity tables and network scope; jurisdiction plumbing/sewer code | Single fixture, branch totals, missing fixture, long/drop/cover/diameter bounds | DFU/gpm/cfs,gravity slope and assigned-flow conservation; PE | Unverified code edition, mixed sewer/dynamic surcharge |
| Q13 Water sizing; water_sizing_engine | Demand curve and declared Hazen–Williams calculation; adopted plumbing/utility code, independently derived unit coefficients | Single pipe, known demand/residual, zero demand, unavailable pressure, C/diameter bounds | gpm/in/psi/ft vs SI, energy head and intermediate rounding; PE | Own formula copied as oracle or all occupancy demand models |
| Q14 Pressure/fire flow; water_sizing_engine graph | Qualified tree/path residuals; independent EPANET network with matched demands/roughness | Tree with elevation, branch, unreachable hydrant, loop rejection, binary search bound | Pressure/head conversion, continuity and source boundary; PE | Shortest-path calculation as general looped-network equilibrium |
| Q15 Vent; vent_engines | Only adopted fixture/table rule where wired and verified; jurisdiction plumbing authority | Branch/table threshold, empty/missing fixture, incompatible joins | Fixture conservation/table units; independently transcribed approved table; plumbing PE | General civil storm/structural analysis or unconnected UI claim |
| Q16 Utility routing; utility_engine | Candidate routes satisfying entered constraints; utility-owner standards/approved surveyed corridor | Crossing/cover/tiein/separation constraints, blocked route, missing depth | Horizontal/vertical units/datum, endpoint connectivity; utilities PE | Public centerline as verified locate/depth |
| Q17 Utility clashes; conflict_engine + siteInterference | Occupied geometry vs reviewed envelopes/common datum; project foundation/profile clearance criteria | Pipe below building clear only with complete evidence; encased pipe/profile, sag, concave/rotated, unknown size/datum | Clearance distance and object identities; broad/narrow phase agreement; PE | Blanket “pipes do not interfere” or inferred foundations |
| Q18 Road/corridor/profile; corridor_engine | Offset geometry, station/grade/crown within domain; approved local/DOT criteria | Straight/curve/intersection, self-crossing/miter limits, profile slope/crown | ft/m,station,grade ratio, offsets and lengths; roadway PE | Superelevation/sight-distance/turning/swept path without separate proof |
| Q19 Cul-de-sac; culDeSacConcept/parametricRoad/current_geometry_export | Tangent concept geometry for bounded R/W, island15ft and fillet20ft; roadway criteria independently reviewed | R35/50/80,W20/30/40/48,rotation/translation/metric, footprint tangency, export parity | Analytical tangency/continuity,0.02ft chord budget,1e-6 comparison only computational; PE | Fire apparatus turning or municipal standard solely from radius |
| Q20 Quantities; quantity_engine/dependencyGraph | Areas/lengths/counts from declared current sources; independently measured analytic objects | Rotated rectangles, polygons holes, line buffers, grouping, combined/hidden objects, overlapping surfaces | ft/sf/cf/m; no double count, source ID/signature, sum components; estimator+PE | Unverified fallback metrics as current or universal pay items |
| Q21 Cost; cost_engine | Quantity x approved effective price book; real permissioned bid/estimate references | 100ft x supplied$125=$12500 arithmetic; missing prices, units/tax/contingency, stale book/currency | Unit/currency/date, subtotal reconciliation; estimator/finance | Alpha fixture prices as market bids or investment accuracy |
| Q22 Subdivision; subdivision_engine | Candidate lot geometry; local adopted parcel/zoning standards and independent survey geometry | Rectangle split, concave site, minimum frontage, exclusions, impossible program | Area/length partition conservation, IDs; surveyor/PE | Legal subdivision approval or land-title truth |
| Q23 Building layouts; building_engine | Footprints/program/placement only, independently measured shapes | L/U/courtyard areas, rotated setback containment, impossible count/overlap | Floor vs footprint units, area/count; architect/PE scope review | Structural/fire/egress approval from layout geometry |
| Q24 Bridge geometry; bridge_engine | Deck/layout geometry only | Straight/skew deck extents, bearings/approach, invalid span/count | Geometry dimensions and coordinate transform; bridge engineer | Load rating, foundations, seismic/stability design |
| Q25 Structural grids; structure_engine | Grid/member-layout primitives only | Bay spacing, duplicate/zero spans, rotations and dimension totals | Length/axis identity; structural reviewer | Steel/rebar/member adequacy, connections or structural analysis |
| Q26 Compliance/QA; compliance_engine,error_check_engine,core/civil_design | Enumerated rules with edition/jurisdiction/input evidence; adopted primary standards | Exact threshold either side, conflicting versions, omitted data and inaccessible-route negative | Unit-consistent thresholds, every rule input/source trace; PE | Blanket code compliance or stamping from a readiness score |
| Q27 Autofix/coordination/optimization | Proposal ranking and bounded rollback only; independently evaluated feasibility | Impossible site, competing constraints, rejected candidate, deterministic seed, no mutation leak | Preserve protected geometry, input/output transaction balance; PE+architect | Global optimum or engineering validity by score alone |
| Q28 Sketch-to-plan | Explicit inferred draft geometry; ground-truth annotated sketch cases | Ambiguous/missing scale, gaps/closed polygons, uncertain primitives | Unknown units remain unknown, geometry provenance; UX/PE | Survey-grade or fabricated dimensions from pixels |
| Q29 AI-assisted actions; parser/chat | Approved intents with deterministic validators and evidence; frozen adversarial corpus | Injection via GIS/PDF, hallucinated standards/elevation, ambiguity, unsupported action/provider outage | Source/units/role/revision invariants, no hidden mutations; security+PE | AI statement as verified calculation, invented sources |
| Q30 Reports/explanations/rendering | Faithful reporting of current reviewed values, no calculation claims from images | Stale/failed/partial result, missing source, chart rounding, 2D vs calculated exports | All displayed values map input/result IDs and units; QA+PE | Attractive image or explanation as professional approval |

## 7. Reference and review procedure

For each Q: record official publication/tool title, publisher, edition/date/section/jurisdiction/amendments and access rights; explain why method applies and unsupported limits. Obtain expected values before showing Civora output, independently checked by another qualified person. Reference software record includes vendor/version/solver settings and input/output files plus license permission; do not assume engineering-grade because two tools agree. Candidate sources include jurisdiction stormwater/utility/DOT manuals, official FHWA hydraulics references, EPA SWMM/EPANET manuals and examples, NRCS hydrology references, adopted accessibility/plumbing criteria, surveyed control datasets and permissioned Civil3D/QGIS/reference CAD cases. No claim these editions/licenses are already current/approved.

Benchmark artifact schema proposed: benchmark_id, Q_family, supported_claim, independent_author/checker, method/reference/version, original_input_files/hashes, expected_values/units, abs/rel_tolerances and rationale, invalid/boundary cases, configuration/CRS/datum, software/engine hashes, observed/differences, conservation residuals, review record/signature, limitations and disposition. Keep private identities/data outside public repo with access-controlled redacted manifest.

No missing reference is filled by asking AI for an authoritative value. Missing professional evidence blocks the affected claim. Reviewers may accept concept geometry but reject engineering analysis; record both distinctly.

## 8. Regression/qualification sequence

1. P01 recreates old failures without editing their old observations.
2. P02 gets semantic/tolerance decisions approved.
3. P03–P06 repair known contracts/math with focused tests, then all affected existing tests.
4. P18 Q children add independent oracles, finite/invalid/property/metamorphic cases and relevant unit/datum coverage.
5. P15 perturbation closure proves recalculation/invalidations through history/export; compare affected partial run to accepted full run.
6. P20 runs two positive scoped projects and negative cases against real isolated backend, not only mocks.
7. P34 verifies advertised files externally, including Z/profile and metric limitations.
8. P19 independent PE acceptance of exact candidate; failure opens linked issue and invalidates downstream scope acceptance.
9. Re-audit repeats on frozen final candidate. Old PASS never certifies newer math.

## 9. Scope and rollback safeguards

Read original projects and results unchanged. New method IDs force stale/review state for affected cached results; do not mark all historical projects “fixed.” Recompute only with explicit user approval and original inputs/sources available. Numeric rollback means suspend affected claims or roll forward, not silently revert to wrong answers. Qualification scope must name geography/data/method/units/format/workload/engine versions. This plan does not authorize construction/permitting, stamp/seal, EOR work or general professional reliance.

