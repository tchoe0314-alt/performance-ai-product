# Current backend regression and failure reconciliation

Application candidate: `692759fd4f884745721a5897719d2d90a4543470`.
No release gate passed. No production/customer data, external requests, paid API,
deployment or package install. Disposable source/SQLite, network/subprocess guard,
new report paths under `/tmp/civora-repair-verification.NBAOtD/results/`.

## Executed evidence

| Report | Outcome | Scope / identity |
|---|---|---|
| broad-155.xml |617 passed,77 subtests,22 warnings,17.15s|All remediation except evidence harness plus affected storage/workflow/privacy/cost suites; SHA256 `89064441b782e2482a0262abd12ecc113c0a0ff25c94bb8f23b9d2546df5cb2a`|
| harness-156.xml |18 passed,4 subtests,0.09s|Evidence harness separately inspected/run; SHA256 `465051f4d401be767a3d8e6ab88a8d478b9a71c87a1b6ee896cbe9ea98026981`|
| backend-157.xml |**2,209 passed /56 failed**,188 passing subtests,56 warnings,418.02s|Remaining backend suite (`tests --ignore=tests/remediation`), NOT clean acceptance; SHA256 `c6ee24af457d51ddf92694e95932bce9fd36ea3378492926aeea4429b02f5a80`|
| queue-fixtures-158.xml |56 passed,30.60s|Queue/revision suites after two fixture-precondition repairs; SHA256 `ecbe3f2c7ffd8ca99fcd9cca6b855c127f73040352cb2534ad08b8f43e1c8266`|

Selections overlap. Do not sum these as unique total tests. The full backend
report records failed assertions/subtest outcomes, not56 separately proven bugs.
Within broad155, all **24 reconstructed original audit cases passed**, none
skipped. Original historical14PASS/10FAIL evidence remains unchanged.

During the long run, content comparison across1,235 tracked Python/TypeScript/JSON
files found zero differences between repository and disposable source. Later only
two positive test fixtures changed; no application code changed in this batch.
The full suite was NOT rerun after those fixtures; targeted158 is the newer evidence.

## Classification of all56 failures

###47 isolation-blocked checks — NOT VERIFIED, not waived

|Module|Failed check outcomes|Boundary|
|---|---:|---|
|test_backend_keepalive_integration|2|Network/socket guard|
|test_backend_service_startup|22|Subprocess guard|
|test_export_vision_ground_truth_dataset|2|Subprocess guard|
|test_golden_load_benchmarks|5|Subprocess guard|
|test_hosted_gauntlet_script|2|Subprocess guard; inspect fake/local behavior before allowing execution|
|test_job_worker_health|2|Network/socket guard|
|test_phase0_inventory|2|Subprocess guard|
|test_release_regression_cleanup_guard|9|Subprocess guard, includes subtest failures|
|test_vision_ai_review_assist|1|Subprocess guard|

Next:review exact commands/fixtures, then qualify these modules with OS sandbox,
owned temporary paths and explicitly owned loopback ports. Never enable arbitrary
network/subprocess access for the whole suite. Guard exceptions are not product
passes and must not be skipped merely to green the release.

###2 obsolete positive fixtures — corrected, targeted verification only

`tests/test_job_queue_service.py`:

- `test_project_list_uses_persisted_has_result_flag`
- `test_project_store_preserves_existing_latest_result_on_empty_save`

Both updated an existing project without its required revision. They now use the
original saved token; no reread-to-force-write, no bypass, unchanged result/flag
oracles. Queue/revision suite158 passes56 tests. Full original failures retained.

###7 engineering failures — OPEN, release-blocking for their claimed scope

|Case|Observed failure family|Required next work|
|---|---|---|
|test_benchmark_suite_regression::test_controlled_benchmarks_preserve_truthful_trust_scores|healthy_clean lacks requested storm deliverables|Trace required export readiness through qualified storm/backwater inputs; keep original oracle|
|test_depth_validators::test_water_depth_requires_pressure_fire_flow_looping_and_velocity|Water readiness false|Reviewed network-demand/supply contract and looped-network solver qualification|
|test_engine_depth_audit::test_complete_water_fixture_proves_water_depth_without_construction_release|review rather than production-depth|Same water-method dependency; do not inflate classification|
|test_manual_mode_validation::test_manual_mode_exposes_ready_storm_export_after_verified_overflow|MANUAL_DELIVERABLES_MISSING /MANUAL_STORM_DELIVERABLE_MATCH|Storm method/reference and actual export readiness, not warning removal|
|test_production_depth_artifacts::test_water_depth_calculates_available_fire_flow_from_residual_pressure|Available fire-flow acceptance|Qualified looped network / independent reference|
|test_production_depth_artifacts::test_water_depth_validates_pressure_fire_flow_hydrants_and_velocity|Pressure/fire-flow ready false|Same water dependency|
|test_water_fire_flow_preview::test_ui_payload_extracts_hydrant_spacing_pressure_zone_and_fire_flow|review rather than pass|Correct upstream water method; retain honest UI state|

These seven are not proven to have seven independent causes. Five relate to water
readiness; two to storm-deliverable acceptance. Current broader evidence supersedes
the earlier six-manual-failure count for this candidate, not the retained reports.
No engineering oracle, unsupported-domain guard or release gate was relaxed.

## Progress and next execution order

1. Corrected the two revision fixtures; verify these again in the next full candidate.
2. Safely execute the47 blocked checks in reviewed isolated lanes.
3. Close the7 engineering failures using qualified methods/reference inputs; reviewer
   request remains pending. Continue other independent remediation while waiting.
4. Run browser interaction/races and PostgreSQL/recovery/performance acceptance.
5. Freeze a new candidate and rerun all required evidence; old reports cannot certify it.

Measured original-audit regression progress: **24/24 (100%)**.
Release approval: **0/5 gates (0%)**. Neither measures overall code completion;
no defensible full-remediation percentage is claimed. Full objective remains active.
