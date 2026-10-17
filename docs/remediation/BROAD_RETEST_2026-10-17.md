# Broad backend rerun — October17

Tested revision: `099e1b524472447b292f2a16044216a5aa495531`.
Original application/test checkout was clean. No source, tests, configuration,
dependencies or expected results were changed. Only this report/evidence is added.
No deployment, hosted request, paid API, real payment or customer data access.

## Results

|Lane|Fresh outcome|Scope|
|---|---|---|
|Strict backend|**2,216 passed /49 failed**,188 passing subtests;398.62s|`tests --ignore=tests/remediation`|
|Remediation|**454 passed**,81 passing subtests;7.46s|All `tests/remediation`, including harness and24 reconstructed audit assertions|
|Reviewed service|**28 passed**;13.69s|Startup, owned local keepalive server, worker health|
|Reviewed tooling|**22 passed**,7 passing subtests;2.44s|Dataset CLI, fake golden-load harness, fake hosted-gauntlet runner, Git fixture inventory, cleanup guards, synthetic image CLI|
|UI auth ordering|**10 scenarios passed**|Actual hook/API code, controlled responses, no network|
|UI auth restoration|**7 scenarios passed**|Actual hook/API classifier, fake fetch/storage|
|TypeScript|**PASS**|`--noEmit --incremental false`, networking and writes denied|

All Python lanes reported0 skips and0 collection errors. There were56 backend,
22 remediation and18 tooling deprecation warnings. Passing tests are not proof of
engineering accuracy or independent usability. Service/tooling overlap the backend
selection: do not add50 to2,216 as if they were all unique tests. Subtest outcomes
and parent case counts differ; the49 failed outcomes occupy43 JUnit parent records.

## Reconciliation of every failure

- **42 isolation-blocked outcomes across36 parent cases**: exact XML
  `(classname,name)` matches show every parent passing in its reviewed lane.
  Zero unmatched blocked cases. `retest-2026-10-17/reconciliation.json` preserves
  the per-case mapping. Original strict failures remain in the archived report.
- **7 genuine engineering acceptance failures**: exactly the same seven as the
  previous report; no additions or closures in this rerun.

|Failure|What remains wrong/unverified|
|---|---|
|`test_benchmark_suite_regression::test_controlled_benchmarks_preserve_truthful_trust_scores`|Healthy fixture still lacks requested storm deliverables|
|`test_manual_mode_validation::test_manual_mode_exposes_ready_storm_export_after_verified_overflow`|Storm plan/export acceptance still returns missing/mismatched deliverables|
|`test_depth_validators::test_water_depth_requires_pressure_fire_flow_looping_and_velocity`|Water readiness false|
|`test_engine_depth_audit::test_complete_water_fixture_proves_water_depth_without_construction_release`|Review rather than production-depth|
|`test_production_depth_artifacts::test_water_depth_calculates_available_fire_flow_from_residual_pressure`|Available fire-flow acceptance fails|
|`test_production_depth_artifacts::test_water_depth_validates_pressure_fire_flow_hydrants_and_velocity`|Pressure/fire-flow readiness false|
|`test_water_fire_flow_preview::test_ui_payload_extracts_hydrant_spacing_pressure_zone_and_fire_flow`|UI reports review rather than pass|

These are five water and two storm acceptance checks, not seven independently
proven root causes. Required next work remains qualified looped-water methods/
demand-supply contracts and qualified storm methods/export propagation with
independent reference evidence. No warning, readiness guard or engineering oracle
was weakened. Professional validation remains unavailable in this run.

### Compared with the earlier2,209/56 run

The improvement to2,216/49 is **not seven new engineering fixes**:

- Two obsolete positive revision fixtures were already repaired and now pass in
  the fresh broad run.
- Five fake golden-load harness cases now run successfully inside this isolation
  policy rather than failing at process isolation. The current policy blocks
  subprocess.Popen/system in the broad lane but permits inherited multiprocessing
  fork under the OS sandbox; network/outside-root writes remain denied.
- All seven engineering failures remain. The older47 blocked outcomes became42,
  with no unsupported inference that a product defect was repaired by guard changes.

## Execution / safety / limits

Tracked files copied to `/tmp/civora-full-retest.HzuOmq/source`. Checksummed dry
rsync comparison of tracked Python,TypeScript,TSX,JSON,CJS files found no source
differences during and after execution. Original HEAD remained the tested revision.
Existing `.venv311` and read-only frontend node_modules were reused; no install.

All Python commands used a sanitized environment, bytecode/cache-provider writes
disabled, owned basetemp/storage/MPL/cache directories, emptyDATABASE_URL and
AI/images/learning disabled. Python guard rejected external .env/database reads.
OS sandbox restricted writes to the owned root (plus/dev/null).

- Broad/remediation: all network denied; Python subprocess/system denied.
- Tooling: all network denied, only reviewed fixture/CLI subprocesses allowed;
  Git system/global configuration disabled. Hosted-gauntlet uses a fake npx, not
  the live site. Golden-load uses fake plans, not production workload proof.
- Service: OS allows only loopback; Python guard permits only ports first bound
  by these tests and propagates ownership to children. Actual local Gunicorn/
  Uvicorn and worker-health servers use disposable data. Startup PostgreSQL tests
  use fake commands, not a PostgreSQL connection.

All runners completed; no leftover test/Gunicorn server was found. The application
was NOT modified to achieve these results. A fresh browser suite, live website,
PostgreSQL concurrency, production restoration, dependency advisory scan, real AI/
GIS providers, independent PE/security/customer acceptance were **not run** here.
This is the requested broad backend rerun, not a repeat of every section of the
comprehensive investor audit or a production readiness certification.

## Durable evidence

Raw XML/logs preserved losslessly as `.gz` under `retest-2026-10-17/`; original
uncompressed reports remain in the disposable root. Compressed artifacts avoid
committing megabytes of repeated captured synthetic stdout. No old evidence is
overwritten. SHA256 of decompressed XML:

|Report|SHA256|
|---|---|
|backend.xml|`874725fdd674e9d4bf353271667b6e4eae0309e46e0d9100b4fcb34a5b64afd3`|
|remediation.xml|`32ddbb78143c40e6d54aba4f0422e91d77bb763e1e51c49dca71c24312e705cd`|
|service.xml|`6d3483e028319a4cf65c9d23d414115f76d6cafb2e1712c0484ef5b2862c1e90`|
|tooling.xml|`a8d261136ad3d3f5e6e473fbf2f86880e0ba43593b2df1fb03ca089b7b336cd1`|

Archives are reports, not executable fixes. The evidence-only commit does not
change the application candidate and cannot certify a later source revision.

## Progress / disposition

- Original audit assertions: **24/24 (100%)**, freshly verified, no skips.
- Seven previously open engineering acceptance failures: **0/7 closed (0%)** in
  this rerun. This is verification, not a repair batch.
- Release gates: **0/5 (0%)** approved. Overall remediation remains incomplete.

Prioritize the seven engineering failures next. Full browser/external acceptance
and the all-session refresh ownership gap also remain required; none is waived.
