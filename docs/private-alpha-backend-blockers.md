# Private Alpha Backend Blocker Register

Last updated: 2026-06-05

## Scope

This register tracks backend issues that still block Civora from being a full-system private alpha. "Full-system private alpha" means the backend can expose the whole Civora engine stack to selected users in review-only mode while staying truthful about missing evidence, assumptions, and construction-release blockers.

This does not mean construction-ready. Construction release remains blocked unless production mode, professional release evidence, current canonical exports, standards, existing conditions, and construction package gates all pass.

## Current Evidence

- Full backend regression on 2026-06-05: `871 passed, 26 warnings`.
- Private-alpha hardening focused regression on 2026-06-05: `86 passed, 22 warnings in 262.03s`.
- Workflow exposure regression on 2026-06-05: `76 passed, 22 warnings in 23.45s`.
- Existing-conditions import/package focused regression on 2026-06-05: `43 passed, 22 warnings in 24.80s`.
- Engine contract registry: 20 engines in `backend/planning/engine_contracts.py`.
- Engine maturity from the current registry:
  - foundation: 2 engines
  - active: 13 engines
  - early: 5 engines
- Current review-only guard evidence:
  - `core/config.py`
  - `backend/planning/construction_package.py`
  - `tests/test_construction_package_manifest.py`
  - `tests/test_application_auth_health_workflows.py`
- Current full-system truth evidence:
  - `backend/planning/engine_readiness.py`
  - `backend/planning/private_alpha_readiness.py`
  - `backend/planning/existing_conditions_package.py`
  - `backend/planning/standards_package.py`
  - `backend/planning/alpha_monitoring.py`
  - `backend/planning/depth_validators.py`
  - `backend/planning/golden_runner.py`
  - `output/dxf_exporter.py`
  - `core/civil_design.py`

## Launch Recommendation

Current backend state: stronger private-alpha candidate, review-only.

Not ready for public beta. Not construction-ready.

The backend can run broad workflows and it now blocks many false-ready paths. It now has first-class alpha readiness, existing-conditions package, standards package, monitoring report, and real-file golden-evidence primitives. The full-system alpha still needs deployed soak evidence, broader real-file golden coverage, and deeper production math in several engines.

## P0 Blockers Before Full-System Private Alpha

### 1. Alpha Readiness Report Must Be Exposed As A First-Class Backend Artifact

Current state:
- `engine_readiness.summary.alpha_readiness` exists in `backend/planning/engine_readiness.py`.
- Tests verify blocked and needs-review rollups in `tests/test_engine_readiness.py`.
- `private_alpha_readiness` now exists in `backend/planning/private_alpha_readiness.py`.
- Planner finalization attaches it to final plan metadata.
- Artifact summaries, run summaries, workflow summaries, dashboards, and project operational summaries now expose compact private-alpha readiness status.

Issue:
- Remaining gap is evidence freshness, not artifact existence: ordinary generated plans remain blocked until current alpha monitoring and golden scenario reports are attached.

Why this blocks full-system alpha:
- Alpha testers need one authoritative backend answer: ready, needs review, or blocked. Today that answer is assembled from several metadata sections.

Required fix:
- Keep the artifact as the single alpha readiness authority.
- Attach current `alpha_monitoring_report` and `golden_scenario_report` during actual alpha backend readiness checks.
- Continue exposing compact status through project/run/artifact summaries.

Evidence needed:
- Covered by `tests/test_private_alpha_readiness.py`.
- Covered by `tests/test_application_project_workflows.py`.
- Covered by `tests/test_application_design_workflows.py`.

Status:
- Mostly closed for infrastructure.
- Still P0 until the alpha readiness check command can generate and persist fresh monitoring and golden reports for a deployment/run.

### 2. Real Existing-Conditions Package Gate Is Not Yet End-To-End Enough

Current state:
- Existing-condition truth checks exist in `core/civil_design.py`.
- Import validation exists in `backend/planning/existing_conditions_importers.py`.
- CSV and LandXML paths have real parsing support.
- Heavy formats are explicitly dependency-gated: DXF survey, Shapefile/GeoPackage, GeoTIFF, LAS/LAZ.
- `existing_conditions_package` now normalizes summary, import validation, source/control metadata, acceptance, and ready/needs_review/blocked status.
- Upload and online existing-condition workflows return `existing_conditions_package`.
- Planner finalization attaches `existing_conditions_package`.

Issue:
- Full alpha still needs more mixed real-file package coverage across larger golden scenarios.
- LandXML terrain surfaces now feed package validation as terrain evidence, while benchmark/datum/control and GIS/source evidence remain required before readiness.
- Dependency-blocked heavy formats now remain visible as failed canonical sources inside import validation and package blockers.
- Heavy import formats may still report blocked requirements when optional libraries are missing.
- Coordinate-system/source/control metadata is correctly required and package acceptance now exists.

Why this blocks full-system alpha:
- Civora's core value depends on real-world site context. Alpha can be review-only, but it still needs truthful and usable import workflows for survey/GIS/terrain packages.

Required fix:
- Add more mixed import package tests that combine survey, GIS, LandXML/DEM, and optional heavy formats under golden scenarios.
- Keep production-grade outputs blocked without survey control, datum, projected coordinate system, and source evidence.

Evidence needed:
- Covered for package builder by `tests/test_existing_conditions_package.py`.
- Covered for upload exposure by `tests/test_application_file_workflows.py`.
- Covered for parser/package validation by `tests/test_existing_conditions_importers.py`.
- LandXML package acceptance and missing-control blockers are covered by `tests/test_existing_conditions_importers.py`.
- Heavy-format dependency-blocked package validation is covered by `tests/test_existing_conditions_importers.py` and upload exposure by `tests/test_application_file_workflows.py`.
- Still needed: larger mixed-import golden fixtures and real imported files for sloped detention, roadway corridor, utility-heavy, floodplain/wetland, and retaining wall scenarios.

Status:
- Mostly closed for the package gate itself.
- Still P0 because full-system alpha needs broader mixed real-file golden coverage, not because LandXML/dependency-blocker package wiring is missing.

### 3. Standards Acceptance Is Truthful But Not Yet Operationally Complete

Current state:
- Standards discovery and acceptance checks exist.
- `civil_design_readiness` blocks fake/trace-less standards.
- Tests cover accepted rule counts and blocked inferred standards.
- `standards_package` now records selected jurisdiction, accepted rules, official sources, company standards, overrides, reviewer notes, status, and production validation.
- Standards acceptance workflow returns `standards_package`.
- Planner finalization attaches `standards_package`.

Issue:
- Live legal/rule discovery is still not implemented as a dependable production source.
- Stale source/version handling and override history need deeper operational coverage.

Why this blocks full-system alpha:
- Alpha can use review-only standards, but must never imply code compliance without explicit accepted standards.

Required fix:
- Keep QA in `needs_review` or `blocked` when standards are inferred, missing, stale, or unaccepted.
- Add stale standards and override-history tests.

Evidence needed:
- Covered for accepted official, inferred/baseline, missing jurisdiction, and missing company standards by `tests/test_standards_package.py`.
- Covered for workflow exposure by `tests/test_application_standards_workflows.py`.
- Still needed: stale standards and user override history tests.

Status:
- Mostly closed for package infrastructure.
- Still P0 until stale/override workflows are covered.

### 4. Golden Scenarios Are Mostly Synthetic, Not Real Imported Projects

Current state:
- `backend/planning/golden_scenarios.py` defines required engines, canonical signals, gates, and payloads.
- `backend/planning/golden_runner.py` checks false production-ready and construction-release claims.
- Golden runner now reports `status`, `passed`, real-file fixture count, synthetic scenario count, and per-scenario import evidence.
- At least one backend test creates real CSV survey and GeoJSON GIS fixture files, builds an accepted existing-conditions package, and feeds that evidence into a golden scenario.

Issue:
- Most golden scenarios still use synthetic payloads instead of realistic imported survey/GIS/terrain files.
- They prove many truth gates, but they do not yet prove real-world import-to-engineering behavior or large-project endurance.

Why this blocks full-system alpha:
- Alpha users will test messy real sites. Synthetic scenarios are not enough to prove backend behavior across the full system.

Required fix:
- Add real-file golden fixtures for:
  - commercial pad
  - multifamily
  - 14-acre mixed use
  - sloped detention
  - roadway corridor
  - utility-heavy site
  - floodplain/wetland constrained site
  - retaining wall site
- Add benchmark pass criteria for runtime, memory, canonical fields, blocked states, and export readiness.

Evidence needed:
- Covered narrowly by `tests/test_golden_runner.py`.
- Load/soak tests with thresholds stored in the scenario definitions.
- Still needed: real-file fixtures for every listed golden scenario and runtime/memory thresholds attached to scenario definitions.

Status:
- Partially closed.
- Still P0 because real-file coverage is not broad enough.

### 5. Deployed Alpha Monitoring Proof Is Missing

Current state:
- Runtime, queue, memory, and lifecycle monitoring are implemented.
- Health workflows expose monitoring and alpha/review-only mode data.
- `alpha_monitoring_report` now applies explicit thresholds to runtime, memory, queue, stale jobs, failed jobs, and process restart evidence.
- Health and debug runtime responses expose `alpha_monitoring_report`.
- `backend/scripts/run_alpha_smoke_soak.py` can generate `alpha_smoke_soak_report_v1` by sampling `/api/debug/runtime` or local process monitoring.

Issue:
- Local tests prove threshold logic, but there is no deployed alpha soak evidence in the repo.
- Thresholds exist in code/env defaults and the smoke/soak command exists, but there is no committed generated report from repeated real backend workflows yet.

Why this blocks full-system alpha:
- Private alpha does not need public scale, but it does need evidence that the backend survives real user workflows without silent crashes or stuck jobs.

Required fix:
- Run the backend smoke/soak command against an actual alpha backend/runtime.
- Store a generated alpha readiness monitoring report artifact.

Evidence needed:
- Covered for report logic by `tests/test_alpha_monitoring.py`.
- Covered for health exposure by `tests/test_application_auth_health_workflows.py`.
- Covered for command/report behavior by `tests/test_alpha_smoke_soak.py`.
- Still needed: generated alpha monitoring report artifact from a repeated backend workflow.

Status:
- Partially closed.
- Still P0 until deployed/local soak evidence is generated and attached from a real backend workflow.

## P1 Blockers Before Public Beta

### 6. Storm/Hydrology Depth Is Guarded But Still Often Review-Only

Current state:
- HGL/EGL, inlet capacity, tailwater, overflow, and detention routing validators exist in `backend/planning/depth_validators.py`.
- Storm production depth enrichment exists in `backend/planning/production_depth.py`.

Issue:
- Validators can block missing evidence, but the generator still relies on simplified/default assumptions for many cases.
- Detention routing requires stronger hydrograph/stage-storage/outlet calculations tied to storm events and standards.

Required fix:
- Implement storm event/hydrograph routing as canonical hydrology evidence.
- Add outlet structure sizing, drawdown, tailwater/backwater, bypass/spread, and overflow path calculations.
- Attach source labels and standards references.

Evidence needed:
- Deterministic tests with known Rational Method and hydrograph outputs.
- Golden scenarios with detention and overflow pass/fail expectations.

### 7. Water Pressure And Fire-Flow Depth Is Early

Current state:
- Water depth validators require pressure zones, hydrant spacing, fire flow, looping, pressure, velocity, and sizing optimization.
- Some pressure graph and sizing logic exists.

Issue:
- Real pressure modeling still needs stronger network hydraulics, source pressure curves, hydrant coverage by standards, and fire-flow residual pressure checks.

Required fix:
- Add real pressure-zone model, residual pressure checks, hydrant spacing standards, velocity limits, and fire-flow demand scenarios.
- Keep review-only when source pressure or jurisdiction fire-flow criteria are missing.

Evidence needed:
- Known network tests for pressure, velocity, looping, and hydrant spacing.

### 8. Roadway/Corridor Depth Is Early

Current state:
- Profiles, sections, crowns, sidewalks, and ADA checks have validators.
- Corridor output can feed profiles/sections.

Issue:
- Roadway realism still needs stronger alignments, intersections, curb returns, crowns, sidewalk/ADA tie-ins, and corridor grading tied to standards.

Required fix:
- Expand roadway geometry and profile model.
- Add curb return/intersection generation with validation.
- Tie crown/cross-slope/sidewalk controls to accepted roadway standards.

Evidence needed:
- Deterministic roadway corridor scenario with profile, sections, ADA, curb returns, and export traceability.

### 9. Export Package Is Strong For DXF Audit, Weak For Civil3D/DWG Confidence

Current state:
- DXF export audit catches stale outputs, canonical ID traceability gaps, concept/fallback sources, and release blockers.
- LandXML IO has tests.

Issue:
- Civil3D/DWG confidence is not production-grade.
- Export package audit needs a unified package manifest for alpha review packages, separate from construction release.

Required fix:
- Add review-package manifest distinct from construction package.
- Add Civil3D/LandXML compatibility checks where implemented and explicit blockers where not.
- Keep DWG export labeled unsupported unless a real DWG path exists.

Evidence needed:
- Tests proving review package artifacts are current, traceable, non-stale, and clearly labeled review-only.

### 10. Production Cost Book Workflow Needs More End-To-End Coverage

Current state:
- Unit price book normalization, CSV import, validation, traceability, and cost blockers exist.

Issue:
- No approved regional cost source library.
- Cost package is not yet fully tied into alpha readiness as a first-class package.

Required fix:
- Add cost package status with price source, effective date, approval, coverage gaps, and quantity model hash.
- Add sample approved CSV fixture and missing-price fixture.

Evidence needed:
- Tests showing traceable costs pass only with approved source and matching quantity hash.

## P2 Improvements After Full-System Private Alpha

### 11. Optional Heavy Import Dependencies Need A Deployment Decision

Issue:
- Shapefile/GeoPackage, GeoTIFF, LAS/LAZ, and DXF survey workflows depend on optional libraries.

Decision needed:
- Bundle them in the backend image or keep them as explicit blocked/unsupported alpha capabilities.

### 12. Standards Online Discovery Needs A Legal/Operational Design

Issue:
- On-the-go standards/law discovery is a future feature and should not be presented as reliable compliance.

Decision needed:
- Choose whether this is a curated standards library, live search with user acceptance, or both.

### 13. Public-Scale Backend Infrastructure Is Still Later

Issue:
- Product foundation docs still call out SQLite/in-process workers as not public-launch infrastructure.

Decision needed:
- Move to production database and durable job queue before public beta.

## Engine-Level Alpha Status

| Engine | Current maturity | Private-alpha status | Main blocker |
| --- | --- | --- | --- |
| Geometry | foundation | usable review-only | Needs stronger topology/buildable-area golden coverage |
| Terrain / Surface | early | blocked without real sources | DEM/LiDAR and survey package evidence |
| Grading | active | usable review-only | More production road/pad/ADA/wall tie-in evidence |
| Drainage | active | usable review-only | More terrain-aware repairs, overflow, blockage evidence |
| Storm Pipe | active | needs review | HGL/EGL, detention/outlet/drawdown, tailwater/backwater depth |
| Sanitary | active | usable review-only | More service coverage/tie-in/reroute proofs on large scenarios |
| Water | early | needs review | Pressure zones, residual pressure, fire-flow, hydrant standards |
| Utility Coordination | active | usable review-only | More protected-zone/trench/ownership realism under real sites |
| Roadway / Corridor | early | needs review | Profiles, crowns, curb returns, intersections, ADA standards |
| Structure | early | scoped review-only | Retaining wall/foundation/bridge interaction depth |
| Earthwork | active | usable review-only | Haul/phasing/wall tradeoff depth |
| Hydrology | active | needs review | Hydrographs, detention routing, overflow/flood routing depth |
| Conflict Resolution | active | usable review-only | Larger cluster optimization/golden proof |
| QA / Validation | active | usable review-only | Fresh monitoring/golden evidence and deeper standards/import edge cases |
| Quantity | active | usable review-only | Cost package and approved price source workflow |
| Export / CAD | active | usable review-only | Review-package manifest, Civil3D/DWG confidence |
| Profile / Section | active | usable review-only | More live linkage tests across real roadway/utility scenarios |
| GIS / Existing Conditions | early | blocked without sources | Broader mixed-import real-file golden coverage |
| AI Orchestration | active | usable review-only | More deterministic rerun/workflow guidance under missing inputs |
| Reactive Model | foundation | usable review-only | Deployed proof and large partial-rerun benchmarks |

## Exact Fix Order

1. Run alpha smoke/soak against a real backend workflow and store the generated `alpha_smoke_soak_report_v1` artifact.
2. Expand real-file golden fixtures beyond the first CSV/GeoJSON package: LandXML, sloped detention, roadway corridor, utility-heavy, floodplain/wetland, retaining wall.
3. Add stale standards and standards override-history tests to `standards_package`.
4. Deepen storm/hydrology detention/outlet/drawdown calculations.
5. Deepen water pressure/fire-flow/hydrant calculations.
6. Deepen roadway/corridor profiles, crowns, curb returns, intersections, and ADA evidence.
7. Add review-package manifest and Civil3D/LandXML/DWG explicit confidence states.
8. Add cost package status and approved unit-price fixture coverage.
9. Add broader load/runtime thresholds to golden scenario definitions.

## Non-Negotiable Truth Rules

- Do not call Civora construction-ready in private alpha.
- Do not remove review-only labels.
- Do not let alpha mode enable construction release.
- Do not treat online maps, public GIS layers, or inferred rules as production evidence without source and acceptance metadata.
- Do not let exports pass when downstream outputs are dirty, stale, invalid, or cache-only.
- Do not let synthetic golden scenarios substitute for real-file import benchmarks.
