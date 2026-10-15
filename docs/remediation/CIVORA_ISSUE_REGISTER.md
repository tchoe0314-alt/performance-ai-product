# CIVORA ISSUE REGISTER

Planning baseline: 2026-10-15, Git `ab7db888e85fb9b6125551ecff769d08e0ca7322`.
**Status: PROPOSED — NOT IMPLEMENTED — NO RELEASE GATE PASSED BY THIS PLAN.**

## 1. Scope, evidence and counting

The full October 15 audit is available in the user-supplied conversation, not as a located standalone committed audit document. The tool transcript contains the 24 original offline assertions; no complete immutable standalone harness was located. Do not recreate an “original” audit file or overwrite prior evidence. Relevant repository evidence is linked below. Current HEAD equals the audited revision; `git diff ab7db888 HEAD` was empty and checkout clean before these planning documents. Therefore no application changes since that revision were identified and no fixes can be credited to newer code. Static inspection reconfirmed the principal mechanisms, not fresh runtime correctness. No application tests, build, migrations, network calls or production access were performed in this planning assignment.

51 unique issue records: **6 confirmed defects, 5 confirmed vulnerabilities, 9 credible unverified risks, 23 missing-verification items, 2 architectural improvements, 2 usability improvements, 3 commercial requirements, 1 missing implementation**. Thus 11 confirmed technical defects/vulnerabilities, not 51 bugs. 32 risk/evidence items remain open; that count includes new reconciliation and requested verification scope, not 32 separately proven original defects. All resolution states are OPEN; no item is fixed/closed by this plan. SEC-10 is an alias of CAN-03, not another counted defect. ENG-06/TEST-02 share program P18 but retain distinct requirements (scope qualification vs independent oracle custody). Efforts are charged once per package in the backlog, never summed per issue.

Severity describes impact if triggered; priority determines execution order. P0 = foundation/safety blocker; P1 = intended beta/public acceptance work; P2 = after safety foundation, before relevant commercial claim; P3 = optional/excluded scope. A High issue with disabled optional feature does not require enabling that feature. Documentation-only unknowns are not proven runtime vulnerabilities.

Evidence classes: C = current source inspection; H = prior execution artifact; D = documentation; T = supplied original transcript, not re-executed now; I = inference; N = unavailable/unauthorized environment. PASS/PARTIAL/FAIL/NOT TESTED/UNKNOWN refer to scoped acceptance, not marketing stage.

## 2. Evidence custody and reconciliation

| Evidence | Current static observation | Boundary |
|---|---|---|
| October 15 full audit | User-supplied text and preceding tool transcript | Original report is not independently signed; source interpretation can be corrected |
| Current code | Exact original audited HEAD, no commit delta | No new code regressions since audit identified; not proof audit found everything |
| Original 24 checks | Reconstructable as A01–A24 in testing plan | Historical 14 PASS/10 FAIL; none newly run here |
| Backend XML | `/tmp/civora-requested-clean-backend-20261014.xml`; SHA256 `cc1b82d9d336cb085c005bbf5da1c8811d79de329d6035149481d5ce9ace13f6`; 2239 testcase nodes, 0 fail/error/skip | Historical; not a new candidate certificate |
| Browser XML | `/tmp/civora-full-browser-20261014.xml`; SHA256 `be9bf0d3912af0ff7c3e51934807c19de213b3cc3e310d23e1bf6addcd5df99c`; 701 testcase nodes, 23 failure children, 0 error children, 15 skipped | Differs from original audit's 700/21 failure/1 error/16 skipped; replacement/reason unknown. Do not merge counts or call improvement/regression |
| Bandit JSON | SHA256 `d114accc59528f3ed7c55dbb483a287afb0e88d1431b8757873153781b1fe6d0` | Filtered findings vs metrics must be distinguished; no security certification |
| Python dependency JSON | SHA256 `2578926764c6e8f9f99d0f41c494d1237cdb5976a7295467e3decdb7658cb7a6` | Historical advisory database/time scope |
| Oct 14 report | `docs/release/full-website-audit-2026-10-14.md` | Contains prior test/deployment/payload claims; does not update October 15 findings |
| PE acceptance | `docs/release/rc1-engineer-uat-packet.md` fields Pending; `docs/product/commercial-pad-benchmark-001.md` pending_human_review | Missing available acceptance evidence, not proof no reviewer exists anywhere |
| Hosted recovery | `docs/release/rc1-hosted-backup-restore-evidence.md` describes Aug 8 drill | Preserve historical success; current DB/files/config not inspected |
| Source rights | `docs/release/evidence-templates/source-rights-review.json` pending | Legal review not completed by code inspection |

Temporary artifacts can disappear; preserving copies is proposed P01 work after execution authorization. Current hashes record observations without modifying originals.

## 3. Audit-to-remediation matrix

Each record below inherits implementation, tests, acceptance, reviewer, risks, rollback, alternatives, dependencies and effort from its explicit P-package in [the backlog](CIVORA_IMPLEMENTATION_BACKLOG.md). This is a normalized issue/task relationship, not an unspecified “fix later.” Sources are repository-relative; line numbers refer to the baseline. Classification/impact is below; package priority is driven by the most urgent linked item.

| ID | Original finding | Classification | Severity / priority | Reconciliation | Package |
|---|---|---|---|---|---|
| ENG-01 | ENG-01; A1 | Confirmed defect | High / P0 | Still exists in code; no fix credited | P03 |
| ENG-02 | ENG-02; A1 | Confirmed defect | High / P0 | Still exists in code; no fix credited | P03 |
| ENG-03 | ENG-03; A2 | Confirmed defect | High / P0 | Still exists in code; no fix credited | P04 |
| ENG-04 | ENG-04; A3 | Confirmed defect | High / P0 | Still exists in code; no fix credited | P06 |
| ENG-05 | ENG-05; A3 | Confirmed defect | High / P0 | Still exists in code; no fix credited | P05 |
| ENG-06 | Audit 5.2-5.4; B3 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P18 |
| CAN-01 | Audit 3,6; canonical 3/5; E1 | Architectural improvement | High / P0 | Open; acceptance/impact not established | P02 |
| CAN-02 | Audit 3.5,6; B2 | Credible unverified risk | High / P1 | Open; acceptance/impact not established | P15 |
| CAN-03 | SEC-10; Audit 6; A6 | Credible unverified risk | High / P0 | Open; acceptance/impact not established | P09 |
| CAN-04 | Audit 6; B1 | Credible unverified risk | High / P1 | Open; acceptance/impact not established | P16 |
| SEC-01 | SEC-01; A4 | Confirmed vulnerability | High / P0 | Still exists in code; no fix credited | P07 |
| SEC-02 | SEC-02; A5 | Confirmed vulnerability | High / P0 | Still exists in code; no fix credited | P08 |
| SEC-03 | SEC-03; A5 | Confirmed vulnerability | High / P0 | Still exists in code; no fix credited | P11 |
| SEC-04 | SEC-04; A5 | Confirmed vulnerability | High / P0 | Still exists in code; no fix credited | P10 |
| SEC-05 | SEC-05; B7 | Credible unverified risk | High / P1 | Open; acceptance/impact not established | P12 |
| SEC-06 | SEC-06; C1 | Credible unverified risk | Medium / P1 | Open; acceptance/impact not established | P08 |
| SEC-07 | SEC-07; C1 | Confirmed vulnerability | Medium / P1 | Still exists in code; no fix credited | P13 |
| SEC-08 | SEC-08; B7 | Confirmed defect | Medium / P1 | Still exists in code; no fix credited | P14 |
| SEC-09 | SEC-09; C1 | Credible unverified risk | Medium / P1 | Open; acceptance/impact not established | P13 |
| SEC-11 | SEC-11; C1 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P17 |
| TEST-01 | Audit 7.1; TEST-01 | Missing verification evidence | High / P0 | Open; acceptance/impact not established | P01 |
| TEST-02 | Audit 5,7; B3 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P18 |
| TEST-03 | Audit 7.4; B2 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P20 |
| TEST-04 | Audit 7,9; B4 | Missing verification evidence | Medium / P1 | Open; acceptance/impact not established | P21 |
| TEST-05 | Audit 7.4,8.4; B5 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P22 |
| TEST-06 | Audit 7.3,11; C2 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P23 |
| TEST-07 | Audit 7.2,12; B4 | Missing verification evidence | High / P0 | Open; acceptance/impact not established | P01 |
| TEST-08 | New reconciliation observation, not new application regression | Missing verification evidence | High / P0 | New evidence discrepancy; not new application defect | P01 |
| OPS-01 | Audit 1,10.3; B5 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P24 |
| OPS-02 | Audit 8.4,10; C2,D2 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P25 |
| OPS-03 | Audit 8; B5 | Credible unverified risk | High / P1 | Open; acceptance/impact not established | P22 |
| OPS-04 | Audit architecture/background work; new static detail | Credible unverified risk | Low / P2 | Open; acceptance/impact not established | P25 |
| UX-01 | Audit 9; B6 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P26 |
| UX-02 | Audit 9; B6 | Usability improvement | High / P1 | Open; acceptance/impact not established | P26 |
| UX-03 | Audit 9; B4 | Usability improvement | Medium / P1 | Open; acceptance/impact not established | P21 |
| COM-01 | Audit 10; D1 | Commercial feature requirement | Medium / P2 | Open; acceptance/impact not established | P28 |
| COM-02 | Audit 10; D1 | Commercial feature requirement | High / P2 | Open; acceptance/impact not established | P29 |
| COM-03 | Audit 10; D1 | Commercial feature requirement | Medium / P2 | Open; acceptance/impact not established | P30 |
| COM-04 | Audit 10; D2 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P31 |
| GOV-01 | Audit 11; C4 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P27 |
| GOV-02 | Audit 11; C4 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P27 |
| GOV-03 | Audit 10,11; C4 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P27 |
| GOV-04 | Audit 5,12; B3 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P19 |
| GOV-05 | Audit 2,11,15; Gate E | Missing verification evidence | Medium / P2 | Open; acceptance/impact not established | P32 |
| ARC-01 | Audit 3,11; E1 | Architectural improvement | Medium / P2 | Open; acceptance/impact not established | P33 |
| EXP-01 | Audit 4.5,7.4; C3 | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P34 |
| EXP-02 | Audit 4.5; capability inventory | Missing implementation | Low / P3 | Open; acceptance/impact not established | P34 |
| EXP-03 | Audit E16; export scope | Missing verification evidence | High / P1 | Open; acceptance/impact not established | P34 |
| AI-01 | Audit 4.4,5.4; E2 | Credible unverified risk | High / P1 | Open; acceptance/impact not established | P35 |
| AI-02 | Audit 4.4,11; E2 | Missing verification evidence | Medium / P2 | Open; acceptance/impact not established | P36 |
| AI-03 | Audit 4.4; E2 | Missing verification evidence | Medium / P3 | Open; acceptance/impact not established | P36 |

## 4. Individual evidence and underlying causes

### ENG-01 — Runoff result contract silently defaults to zero

- **Original:** ENG-01; A1.
- **Evidence:** `engines/hydrology_engine.py:18; backend/planning/runtime.py:947; planner.py:9989; backend/application/job_workflows.py:1670`.
- **Cause / strongest supported hypothesis:** Result owns total_runoff_cfs; adapter requests total_flow_cfs using a zero default. Caller tracing also finds C/I consumed independently; do not infer all pipes use the wrong peak.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P03; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### ENG-02 — Hydrology domain and finite-input validation

- **Original:** ENG-02; A1.
- **Evidence:** `engines/hydrology_engine.py:7-36; backend/planning/runtime.py:948-953`.
- **Cause / strongest supported hypothesis:** Engine unconditionally returns success; planner clamps area and estimates Tc/C/intensity rather than requiring sourced engineering inputs.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P03; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### ENG-03 — Detention geometry, curve and routing consistency

- **Original:** ENG-03; A2.
- **Evidence:** `engines/detention_engine.py:146-189,192-249,260-303`.
- **Cause / strongest supported hypothesis:** Geometric-mean frustum is not the integral for every expanding unequal rectangle; stage accumulation uses another approximation. Routing caps elevation beyond curve without explicit overflow model.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P04; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### ENG-04 — Node/cell earthwork integration mismatch

- **Original:** ENG-04; A3.
- **Evidence:** `engines/surface_engine.py:650; engines/earthwork_engine.py:277; engines/grading_engine.py:689; tests/test_real_math_big_pass.py:138`.
- **Cause / strongest supported hypothesis:** Surface constructors are node-inclusive; both volume paths assign a full cell to each node. Some existing fixtures encode a competing convention.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P06; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### ENG-05 — Spatial surface compatibility is incomplete

- **Original:** ENG-05; A3.
- **Evidence:** `engines/earthwork_engine.py:140-214; engines/surface_engine.py:150`.
- **Cause / strongest supported hypothesis:** Matching dimensions and spacing are accepted without checking origins/bounds; GridSurface lacks complete CRS/datum/orientation metadata.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P05; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### ENG-06 — Independent validation missing across supported disciplines

- **Original:** Audit 5.2-5.4; B3.
- **Evidence:** `engines/; backend/planning/engine_contracts.py; docs/product/commercial-pad-benchmark-001.md; docs/release/rc1-engineer-uat-packet.md`.
- **Cause / strongest supported hypothesis:** Internal tests/contract declarations do not constitute independent numerical or professional acceptance.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P18; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### CAN-01 — Engineering representation ownership boundaries

- **Original:** Audit 3,6; canonical 3/5; E1.
- **Evidence:** `backend/services/canonical_project.py:13; canonical_record.py:23; canonical_canvas.py; apps/web/app/utils/canonicalCanvasProject.ts; core/geometry_core.py; core/project_manager.py`.
- **Cause / strongest supported hypothesis:** Aggregate ownership exists alongside compatibility inputs and computed models; projections require explicit ownership/version contracts rather than a rewrite.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P02; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### CAN-02 — Dependency propagation and stale/export invariants

- **Original:** Audit 3.5,6; B2.
- **Evidence:** `backend/services/dependency_graph.py; backend/planning/reactive_model.py:83,370; apps/web/app/utils/dependencyGraph.ts; canonicalDependencyPolicies.ts; backend/application/artifact_workflows.py:26`.
- **Cause / strongest supported hypothesis:** Selected links and stage rules exist; complete elevation/profile/quantity/cost/dimension propagation has not been proven.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P15; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### CAN-03 — All-writer concurrency and stale record updates

- **Original:** SEC-10; Audit 6; A6.
- **Evidence:** `backend/services/project_revision.py:31; backend/services/project_store.py:870; backend/application/chat_workflows.py:5600; backend/application/project_snapshot.py`.
- **Cause / strongest supported hypothesis:** Revision-aware wrapper already protects some paths. Direct chat full-record save still omits expected revision; lost-update consequence requires race proof.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P09; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### CAN-04 — Duplicated execution snapshots and payload growth

- **Original:** Audit 6; B1.
- **Evidence:** `backend/application/job_workflows.py:177-195; backend/services/canonical_record.py:23-34; apps/web/app/utils/canonicalCanvasProject.ts:89; docs/release/full-website-audit-2026-10-14.md`.
- **Cause / strongest supported hypothesis:** Request/checkpoint copies are retained in editable controls and metadata. Historical 17 MB input/8.5 MB result observation is not a fresh measurement.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P16; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-01 — Caller-controlled GIS outbound destinations

- **Original:** SEC-01; A4.
- **Evidence:** `backend/api/app.py:1678; backend/application/file_workflows.py:490; backend/planning/gis_provider_registry.py:717,797; existing_conditions_online.py:102`.
- **Cause / strongest supported hypothesis:** Authenticated URL input flows into requests.get without destination restriction. Impact depends on network reachability; no live compromise is asserted.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P07; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-02 — Arbitrary bearer text rotates authentication throttle keys

- **Original:** SEC-02; A5.
- **Evidence:** `backend/api/app.py:266-302,1400`.
- **Cause / strongest supported hypothesis:** Throttle keys include an unvalidated bearer hash before login authentication, allowing distinct buckets from a constant source.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P08; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-03 — Unverified address can be granted another person's invitation

- **Original:** SEC-03; A5.
- **Evidence:** `backend/services/auth_store.py:47-98; backend/services/project_store.py:1167-1217; backend/api/app.py:225`.
- **Cause / strongest supported hypothesis:** Registration creates authenticated identity without email proof; inviting an existing matching email grants membership immediately. Owner invitation is a precondition.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P11; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-04 — Raw non-expiring persisted session tokens

- **Original:** SEC-04; A5.
- **Evidence:** `backend/services/auth_store.py:115-139,177-188; backend/services/database.py; apps/web/app/utils/auth.ts`.
- **Cause / strongest supported hypothesis:** Bearer credentials are stored as lookup values without enforced lifetime. Database disclosure enables token use; no disclosure is claimed.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P10; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-05 — Learning collection may bypass individual consent

- **Original:** SEC-05; B7.
- **Evidence:** `backend/services/chat_learning_store.py:18-60; backend/application/chat_workflows.py:5621; backend/services/project_store.py:1755`.
- **Cause / strongest supported hypothesis:** Global flag gates collection; collection function has no user/org consent parameter. Default disabled limits present exposure; deployment setting unknown.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P12; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-06 — Forwarded identity/distributed throttling and bucket retention

- **Original:** SEC-06; C1.
- **Evidence:** `backend/api/app.py:248-302; start_backend_api.sh; railway.toml`.
- **Cause / strongest supported hypothesis:** Forwarded IP trusted directly; counters are process-local and key dictionary has no global TTL. Exploitability depends on proxy/deployment.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P08; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-07 — Operational diagnostics exposed to ordinary authenticated users

- **Original:** SEC-07; C1.
- **Evidence:** `backend/api/app.py:1353-1368; backend/application/production_env_validator_v1.py`.
- **Cause / strongest supported hypothesis:** Endpoints require a user but no operator role. This is excess operational disclosure, not proof that secret values leak.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P13; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-08 — Upload name reuse and cleanup can destroy prior source

- **Original:** SEC-08; B7.
- **Evidence:** `backend/application/file_workflows.py:130-147,165-177; backend/services/artifact_service.py`.
- **Cause / strongest supported hypothesis:** Existing user/filename path opens with wb and HTTP-error cleanup unlinks it; prior bytes are not protected. No destructive test performed.
- **State:** OPEN. C supports the defect/control gap; earlier T supplies selected runtime evidence. No new execution here.
- **Repair / verification ticket:** P14; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-09 — Browser session/XSS/CSRF policy needs qualification

- **Original:** SEC-09; C1.
- **Evidence:** `apps/web/app/utils/auth.ts:7; apps/web/next.config.ts:25; apps/web/app/layout.tsx; backend/api/app.py:832`.
- **Cause / strongest supported hypothesis:** Session storage is script-readable; inspected headers omit CSP. No XSS established; cookie migration would introduce CSRF obligations; edge controls unknown.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P13; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### SEC-11 — Current full dependency/container/action exposure unknown

- **Original:** SEC-11; C1.
- **Evidence:** `requirements_backend.txt; apps/web/package-lock.json; Dockerfile; Dockerfile.backend; .github/workflows/; docs/release/full-website-audit-2026-10-14.md`.
- **Cause / strongest supported hypothesis:** Historical dev findings and filtered scans cannot certify current full dependency graph; no network advisory queries authorized here.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P17; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-01 — Original 24 checks are transcript-only acceptance evidence

- **Original:** Audit 7.1; TEST-01.
- **Evidence:** `User-supplied October 15 audit and tool transcript; no standalone October 15 audit/report harness located under docs/`.
- **Cause / strongest supported hypothesis:** Inputs/outcomes can be reconstructed, but no immutable complete executable original harness was located; preserve uncertainty.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P01; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-02 — Independent golden oracle program

- **Original:** Audit 5,7; B3.
- **Evidence:** `tests/test_real_math_big_pass.py; tests/test_real_math_hydraulics.py; backend/fixtures/golden/; benchmark-spec.json`.
- **Cause / strongest supported hypothesis:** Some tests call the same engine helper for expected values. This is regression evidence, not independent correctness proof.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P18; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-03 — Positive connected engineering acceptance incomplete

- **Original:** Audit 7.4; B2.
- **Evidence:** `backend/application/commercial_site_benchmark.py; apps/web/tests/live/; docs/release/pilot-connected-verification-2026-10-14.md`.
- **Cause / strongest supported hypothesis:** Drawing-only, failure-blocking and synthetic flows do not prove valid full calculated deliverables.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P20; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-04 — Repeatable browser/accessibility acceptance unresolved

- **Original:** Audit 7,9; B4.
- **Evidence:** `apps/web/playwright.config.ts; playwright.full-audit.config.ts; apps/web/tests/live/; docs/release/full-website-audit-2026-10-14.md`.
- **Cause / strongest supported hypothesis:** Product/test/environment/flaky failures need separate dispositions; Firefox support not proven.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P21; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-05 — Current complete DB/file/job restore acceptance

- **Original:** Audit 7.4,8.4; B5.
- **Evidence:** `backend/services/backup_restore.py; data_lifecycle.py; docs/release/rc1-hosted-backup-restore-evidence.md`.
- **Cause / strongest supported hypothesis:** August drill documents historical PostgreSQL recovery; current release, artifact files and job semantics remain unverified.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P22; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-06 — Measured capacity, latency and cost envelope

- **Original:** Audit 7.3,11; C2.
- **Evidence:** `backend/application/golden_load_benchmarks.py; engines/conflict_engine.py; apps/web/app/utils/performanceProbes.ts; backend/services/job_queue.py`.
- **Cause / strongest supported hypothesis:** Historical bounded local load is not a representative production operating envelope.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P23; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-07 — Immutable release/engineering/config evidence linkage

- **Original:** Audit 7.2,12; B4.
- **Evidence:** `apps/web/app/api/release-identity/route.ts; backend/api/app.py; .github/workflows/; docs/release/`.
- **Cause / strongest supported hypothesis:** Release identity code exists, but prior artifacts are not acceptance of the exact next deployed candidate.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P01; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### TEST-08 — Browser evidence path now differs from cited baseline

- **Original:** New reconciliation observation, not new application regression.
- **Evidence:** `/tmp/civora-full-browser-20261014.xml; docs/release/full-website-audit-2026-10-14.md`.
- **Cause / strongest supported hypothesis:** Current file has 701 testcase entries, 23 failure children, 0 error children, 15 skipped; original audit cited 700/21/1/16. Reason/source replacement unknown.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P01; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### OPS-01 — Deployed identity and invitation policy not currently verified

- **Original:** Audit 1,10.3; B5.
- **Evidence:** `backend/api/app.py:225; railway.toml; apps/web/app/api/release-identity/route.ts; docs/product/free-invitation-pilot-decisions-2026-10-14.md`.
- **Cause / strongest supported hypothesis:** Local code honors explicit closed signup but defaults private_alpha to public registration; current provider settings not inspected.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P24; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### OPS-02 — Alerting, incident and support ownership

- **Original:** Audit 8.4,10; C2,D2.
- **Evidence:** `backend/application/memory_logging.py; backend/services/support_store.py; docs/release/rc1-incident-runbook.md; rc1-operations-runbook.md`.
- **Cause / strongest supported hypothesis:** Runbooks/metrics exist, but actionable alert delivery, staffed ownership and incident execution not established.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P25; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### OPS-03 — Migration and rollback compatibility

- **Original:** Audit 8; B5.
- **Evidence:** `backend/services/database.py:744; backend/application/project_snapshot.py; Dockerfile.backend; start_backend_api.sh`.
- **Cause / strongest supported hypothesis:** Additive startup DDL and JSON-version changes need concurrent-start and old/new writer compatibility proof, not an assumed safe code revert.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P22; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### OPS-04 — Scheduled learning route/method wiring

- **Original:** Audit architecture/background work; new static detail.
- **Evidence:** `vercel.json; apps/web/next.config.ts:17; backend/api/app.py:2441`.
- **Cause / strongest supported hypothesis:** Vercel cron path targets frontend while inspected handler is authenticated backend POST; no corresponding Next route located. Deployment routing may differ; learning stays off.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P25; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### UX-01 — Independent engineer task completion not established

- **Original:** Audit 9; B6.
- **Evidence:** `docs/release/rc1-engineer-uat-packet.md; apps/web/app/components/; apps/web/app/PerformanceAIDashboardView.tsx`.
- **Cause / strongest supported hypothesis:** Pending UAT cannot establish unaided use or correct interpretation of engineering states.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P26; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### UX-02 — Units/sources/export-scope and warning comprehension

- **Original:** Audit 9; B6.
- **Evidence:** `apps/web/app/components/SourceConfidencePanel.tsx; DeliverPanel.tsx; backend/application/current_geometry_export.py`.
- **Cause / strongest supported hypothesis:** Dense controls and differing current/review/calculated states may induce mistaken reliance; actual confusion not yet observed in independent testing.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P26; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### UX-03 — Layout, accessibility and supported-device evidence

- **Original:** Audit 9; B4.
- **Evidence:** `apps/web/tests/live/; apps/web/app/components/Preview2DCanvasShell.tsx; next.config.ts`.
- **Cause / strongest supported hypothesis:** Historical scans cover selected states, not primary workflows, assistive technologies and large-project responsiveness.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P21; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### COM-01 — Purchasable subscriptions and lifecycle missing

- **Original:** Audit 10; D1.
- **Evidence:** `backend/services/billing.py:69-104; apps/web/app/upgrades/page.tsx`.
- **Cause / strongest supported hypothesis:** Stripe class is status-only; proposed Pro/Engineer/Teams/Enterprise catalog is not operational checkout.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P28; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### COM-02 — Server-side entitlement/usage enforcement missing

- **Original:** Audit 10; D1.
- **Evidence:** `backend/services/billing.py:253; backend/api/app.py; backend/services/job_queue.py`.
- **Cause / strongest supported hypothesis:** Usage gate always permits; paid status and async jobs need transactional authoritative checks, not UI gates.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P29; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### COM-03 — Organization seats and billing administration

- **Original:** Audit 10; D1.
- **Evidence:** `backend/services/project_store.py; database.py; billing.py; apps/web/app/components/ProjectTeamMemoryPanel.tsx`.
- **Cause / strongest supported hypothesis:** Project sharing is not a billable-seat lifecycle or complete organization billing model.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P30; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### COM-04 — Customer support/account lifecycle and commercial acceptance

- **Original:** Audit 10; D2.
- **Evidence:** `backend/services/support_store.py; data_lifecycle.py; apps/web/app/support/; docs/release/`.
- **Cause / strongest supported hypothesis:** Intake and lifecycle code exist; monitored response, full export/deletion and paid onboarding unverified.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P31; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### GOV-01 — GIS/survey/model data rights

- **Original:** Audit 11; C4.
- **Evidence:** `docs/release/evidence-templates/source-rights-review.json; backend/services/brief_sources.py; GIS provider registry`.
- **Cause / strongest supported hypothesis:** Rights review template pending; public endpoint availability does not establish retention/redistribution/model-training permission.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P27; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### GOV-02 — Software/contributor/model IP chain of title

- **Original:** Audit 11; C4.
- **Evidence:** `Git history; dependency manifests; vision/; investor-kit/ (claims not verified)`.
- **Cause / strongest supported hypothesis:** Contributor assignments, license notices and model/data provenance not established from repository alone.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P27; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### GOV-03 — Customer legal/privacy/professional scope

- **Original:** Audit 10,11; C4.
- **Evidence:** `backend/services/billing.py; core/professional_release.py; docs/release/rc1-engineer-uat-packet.md`.
- **Cause / strongest supported hypothesis:** Configured URLs/reviewer metadata cannot prove signed terms, professional approval, liability allocation or appropriate insurance.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P27; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### GOV-04 — Independent PE review and claimed capability limits

- **Original:** Audit 5,12; B3.
- **Evidence:** `docs/product/commercial-pad-benchmark-001.md; docs/release/rc1-engineer-uat-packet.md; core/professional_release.py`.
- **Cause / strongest supported hypothesis:** Independent reviewer acceptance remains pending; code gates do not authenticate professional judgment.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P19; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### GOV-05 — Investor/customer traction and economics evidence

- **Original:** Audit 2,11,15; Gate E.
- **Evidence:** `docs/release/pilot-external-review-handoff-2026-10-13.md; investor materials existence only`.
- **Cause / strongest supported hypothesis:** No independently established retention, purchasing behavior, measured customer value or unit economics.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P32; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### ARC-01 — Oversized orchestration and duplicated contracts

- **Original:** Audit 3,11; E1.
- **Evidence:** `planner.py; planner_orchestrator.py; backend/api/app.py; backend/application/chat_workflows.py; apps/web/app/PerformanceAIDashboardView.tsx`.
- **Cause / strongest supported hypothesis:** Compatibility and orchestration accumulated across large modules; targeted boundary extraction preferable to a wholesale rewrite.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P33; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### EXP-01 — External DXF/LandXML/print acceptance

- **Original:** Audit 4.5,7.4; C3.
- **Evidence:** `output/dxf_exporter.py:4350; backend/planning/export_external_verification.py; backend/services/artifact_service.py`.
- **Cause / strongest supported hypothesis:** Internal parsing/roundtrips cannot establish advertised target-tool fidelity, units or plotted scales.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P34; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### EXP-02 — Native DWG/Civil3D scope absent

- **Original:** Audit 4.5; capability inventory.
- **Evidence:** `backend/planning/dwg_compatibility.py:9`.
- **Cause / strongest supported hypothesis:** Native writer explicitly unsupported. Honest exclusion is an acceptable release disposition; conversion/licensing is a separate decision.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P34; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### EXP-03 — LandXML lossy geometry and metric limitations

- **Original:** Audit E16; export scope.
- **Evidence:** `backend/planning/landxml_io.py:165-210; backend/services/artifact_service.py:479`.
- **Cause / strongest supported hypothesis:** Feet-only writer emits centerline Z=0; must qualify as explicitly 2D review interchange or implement independently verified profile export; do not promise native CAD semantics.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P34; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### AI-01 — Assumption/fabrication and semantic command safety

- **Original:** Audit 4.4,5.4; E2.
- **Evidence:** `parsers/ai_parser.py:384,1929; backend/application/chat_workflows.py; backend/planning/ai_orchestration_evidence.py`.
- **Cause / strongest supported hypothesis:** Structured JSON and concept defaults do not prove factual values or protect every downstream action from untrusted context.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P35; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### AI-02 — Real provider/imagery quality and cost acceptance

- **Original:** Audit 4.4,11; E2.
- **Evidence:** `backend/ai/provider.py; image_provider.py; backend/application/ai_visualization_workflows.py`.
- **Cause / strongest supported hypothesis:** Mock and disabled-provider tests cannot prove actual image fidelity, reliability or cost; paid execution needs explicit budget approval.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P36; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

### AI-03 — Learning/shadow/promotion effectiveness

- **Original:** Audit 4.4; E2.
- **Evidence:** `backend/services/chat_learning_pipeline.py; backend/planning/vision_shadow_evaluation.py; vision/`.
- **Cause / strongest supported hypothesis:** Tooling exists; quality, leakage prevention and safe promotion evidence not established; keep disabled/out of beta scope unless qualified.
- **State:** OPEN. C/D/H/I as described; runtime consequence or required acceptance remains NOT TESTED/UNKNOWN.
- **Repair / verification ticket:** P36; strategy, alternatives, dependencies, independent assertions, risks, rollback, reviewer and effort are binding fields in that package. No blanket resolution based on an old passing test.

## 5. Complete original-audit disposition

| Original audit coverage / roadmap | Remediation disposition |
|---|---|
| A1 | ENG-01/02 → P03; preserve true zero and trace all callers |
| A2 | ENG-03 → P04 |
| A3 | ENG-04/05 → P05/P06, with P02 numerical approval |
| A4 | SEC-01 → P07 |
| A5 | SEC-02/03/04/06 → P08/P10/P11 |
| A6 | CAN-03 and SEC-10 alias → P09; existing project_snapshot wrapper is already revision-aware, do not replace it as “missing” |
| B1 | CAN-04 → P16; historical size is not a fresh budget measurement |
| B2 | CAN-02/TEST-03 → P15/P20 |
| B3 | ENG-06/TEST-02/GOV-04 → P18/P19 |
| B4 | TEST-01/04/07/08, UX-03 → P01/P21 |
| B5 | TEST-05, OPS-01/03 → P22/P24; do not erase August restore evidence |
| B6 | UX-01/02/03 → P26/P21 |
| B7 | SEC-05/08, GOV-01 → P12/P14/P27 |
| C1 | SEC-07/09/11 → P13/P17 and independent review |
| C2 | TEST-06/OPS-02 → P23/P25 |
| C3 | EXP-01/02/03 → P34; native DWG/Civil3D can remain explicitly unsupported |
| C4 | GOV-01/02/03 → P27 |
| D1 | COM-01/02/03 → P28/P29/P30; not required for free pilot |
| D2 | COM-04 → P31; minimal pilot support through P25 |
| E1 | ARC-01 → P33; incremental optional refactoring, no rewrite |
| E2 | AI-01/02/03, GOV-05 → P35/P36/P32 |
| All project/template/group/undo/save/history features | Preservation and perturbation journeys P09/P15/P20; no wholesale reimplementation |
| All GIS/parcel/terrain/CRS/utility/source features | P05/P07/P14/P18/P27; geography availability not assumed |
| All engineering engines and quantities/cost/compliance | Q-family matrix under P18; geometry generation distinguished from professional analysis |
| All exports/print/report/unit features | P20/P34; advertised compatibility only after independent acceptance |
| All AI/memory/learning/image features | P12/P35/P36; disabled/mock is not production evidence |
| Accounts/org/roles/support/analytics/traction | P08–P13/P25–P32; source counts do not establish customers |
| Investor stage/rating statements | Remain original scoped opinion, not a new stage certification; final re-audit must reassess |

Corrections/qualifications: hydrology peak field bug is real but downstream C/I paths may compute flow separately; partial canonical integration is not absence of a canonical document; unknown edge CSP is not demonstrated XSS; raw-token storage is not proof of leaked credentials; absent native DWG need not block honest DXF/PDF launch; existing private-alpha explicit signup flag works, while default and hosted policy still need qualification. No original finding has been discarded.

