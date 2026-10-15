# CIVORA IMPLEMENTATION BACKLOG


## Additive all-feature audit instructions

P01 additionally owns a repository-wide capability/flag/route/control/provider inventory and safe-execution classification before any feature is enabled. P20 additionally owns the all-feature characterization/interaction lane specified in the testing plan. Initial inventory may proceed before all P20 engineering dependencies; final integrated acceptance cannot. Treat mocked, missing and blocked modes separately; do not substitute adapters for real provider quality. Scope any discovered new fix into the existing linked package or a new reviewed child ticket. No code or configuration enablement occurred in this planning task.

Fresh execution prompt supplement for P01/P20: “Inventory every implemented and disabled Civora feature and record source/enablement/side-effect prerequisites. In an explicitly authorized isolated environment, exercise each safe implemented mode and high-risk combinations; keep production, paid providers, real payments, existing data and learning collection disabled. Mark missing/mock/blocked states honestly. File distinct root-cause issues, preserve evidence, and continue the current remediation dependency order. Retest affected functionality after fixes and run a fresh full supported-feature sweep at gates. Do not enable everything on the live site or bypass security/release checks.”

Planning baseline: 2026-10-15, Git `ab7db888e85fb9b6125551ecff769d08e0ca7322`.
**Status: PROPOSED — NOT IMPLEMENTED — NO RELEASE GATE PASSED BY THIS PLAN.**

## Portfolio summary

36 parent packages govern 51 unique issues. P18 is a qualification program, not a single giant coding change; P33 is an extraction program; each must use child packages. Workstream totals and dependencies are in the master plan. Direct estimate **294–586 engineer-days**; reserve 25–40% for newly discovered defects/integration yields approximately **370–820 engineer-days**. External PE/legal/CAD/security review time, recruitment, calendar waiting, fees and hosting costs are not included. No engineer-day sum is a delivery date.

## Execution contract applying to every package

This is a proposed backlog, not execution authorization. Work starts only on explicit user approval for a named package. Tests write temporary databases/files/caches unless proven otherwise: authorize a disposable local environment first; no production/customer data, network, installs, migrations, paid calls, deployment or commits are implied by package approval. Separate explicit approval is required for deployment, provider/spend access, schema/engineering-semantic decisions and migrations. Stop on unexpected dirty files or changing HEAD; preserve user work.

**Preconditions:** read the master plan, issue register and domain plan; confirm current HEAD, applicable AGENTS.md, dependency package acceptance evidence, and approved ADRs. Reinspect target files because baseline line numbers will drift. Missing evidence means blocked acceptance, not permission to improvise.

**Allowed changes:** only listed target modules, their directly required tests and package documentation on an approved working branch. Abbreviated sibling basenames refer to the same named directory. Broad directory targets in umbrella packages must be replaced by a <=10 engineer-day child allowlist before coding. New schema/config/dependency changes require a separately approved migration/design plan.

**Explicit out of scope:** unrelated files/features, public claims, real customer records, purchases, provider calls, existing audit artifacts, billing in safety packages, unrelated numerical assumptions, and mass refactors. Preserve v1 projects, object IDs, geometry, source hashes, edit/calculation/review history and permitted file formats. No automatic bulk recalculation or replacement of historical results.

**Verification command templates (future, NOT RUN):** after creating an authorized disposable local environment and new output directory, use `PYTHONDONTWRITEBYTECODE=1 <approved-python> -B -m pytest -p no:cacheprovider --basetemp <new-disposable-temp> tests/remediation/test_pNN.py <reviewed-existing-affected-tests> --junitxml <new-evidence-dir>/pNN.xml`. Each `test_pNN.py` is a **proposed new path**, not an existing test. Select existing test paths using `rg --files tests`, review imports/fixtures first. Frontend packages additionally use `node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false` and approved isolated `node node_modules/@playwright/test/cli.js test --config <reviewed-local-only-config> <package-spec>`; these may write artifacts and launch mutating local services. Do not execute until authorized. P01/P02 planning/static steps can instead use read-only git/rg/AST checks. Do not invoke npm prebuild/clean or an arbitrary pytest collection against existing storage. Shell placeholders are not executable commands until resolved and validated.

**Completion report:** package/issues; original vs resulting revision; exact files and why; expected oracle provenance; tests/commands and pass/fail/skip counts with unique evidence paths/hashes; model/engine/dependency/config versions; old-project compatibility; conflicts/side effects; reviewer and approvals; rollback rehearsal; remaining limits; proposed gate disposition. Completion is not gate approval. An unreviewed/failed/blocked assertion cannot be marked resolved. Revert only package-owned commits after user authorization; never git reset --hard or restore a whole database as a casual code rollback.

**Branch/commit proposal:** one `remediation/pNN-short-name` branch per approved package, rooted at recorded candidate; tests and repair in small reviewable commits, migrations separated expand/write/contract. No branch or commit created by this plan. Merge only after domain review and dependent acceptance; freeze a new immutable RC after merges, rerun all relevant evidence. No parallel edits to shared files without file ownership coordination.

## Ordered package index

| Package | Workstream | Issues | Effort (engineer-days) | Dependencies | Gate |
|---|---|---|---|---|---|
| P01 Preserve audit cases and immutable release evidence | Testing | TEST-01, TEST-07, TEST-08 | 3–5 | None | A,B,C,D,E |
| P02 Approve model, numerical and surface decisions | Canonical | CAN-01 | 4–7 | P01 | A,B,E |
| P03 Repair hydrology result contract and invalid-input handling | Engineering | ENG-01, ENG-02 | 4–8 | P01, P02 | A,B |
| P04 Unify detention volume, curves and conservative routing | Engineering | ENG-03 | 6–12 | P02, P03 | A,B |
| P05 Introduce explicit surface compatibility and registration | Engineering | ENG-05 | 5–10 | P02 | A,B |
| P06 Correct grid/TIN earthwork integration and factor order | Engineering | ENG-04 | 8–16 | P02, P05 | A,B |
| P07 Constrain GIS and other outbound network requests | Security | SEC-01 | 4–8 | P01 | B,C |
| P08 Stable authentication and distributed abuse controls | Security | SEC-02, SEC-06 | 6–12 | P01 | B,C |
| P09 Make design writes conflict-safe across every writer | Canonical | CAN-03 | 8–16 | P01, P02 | B,C |
| P10 Migrate session storage, expiry and revocation safely | Security | SEC-04 | 5–10 | P01, P02 | B,C |
| P11 Verify enrollment, invitations and organization identity | Security | SEC-03 | 6–12 | P08, P10 | B,C,D |
| P12 Enforce consent at learning collection and lifecycle boundaries | Security | SEC-05 | 4–8 | P09, P11 | B if enabled; C,D |
| P13 Harden operator diagnostics and browser trust boundary | Security | SEC-07, SEC-09 | 5–10 | P10 | B,C |
| P14 Make uploaded sources immutable and failure-safe | Security | SEC-08 | 4–8 | P02, P09 | B,C |
| P15 Verify explicit engineering dependency/change contracts | Canonical | CAN-02 | 8–16 | P02, P03, P05, P06, P09 | A(scope),B,C |
| P16 Separate editable data, execution state and archival growth | Canonical | CAN-04 | 8–16 | P02, P09, P15 | B,C |
| P17 Qualify software supply chain and dependency exposure | Security | SEC-11 | 4–8 | P01 | B,C,D,E |
| P18 Build independent engine-family qualification packs | Engineering | ENG-06, TEST-02 | 75–150 | P02, P03, P04, P05, P06, P15 | A per scope,B,C,E |
| P19 Obtain independent scope-specific professional acceptance | Governance | GOV-04 | 6–12 | P18, P20, P27, P34 | B,C,E |
| P20 Complete positive and negative connected engineering journeys | Testing | TEST-03 | 10–20 | P03, P04, P05, P06, P09, P14, P15, P16, P18 | B,C,D |
| P21 Stabilize supported-browser/accessibility acceptance | UX | TEST-04, UX-03 | 6–12 | P09, P15, P20 | B scoped,C |
| P22 Qualify recovery, migrations and reversible deployment | Operations | TEST-05, OPS-03 | 8–16 | P09, P10, P14, P16, P01 | B,C,D |
| P23 Measure operating envelope and unit economics | Operations | TEST-06 | 8–16 | P16, P20, P22 | B scoped,C,D,E |
| P24 Verify exact hosted candidate and controlled enrollment | Operations | OPS-01 | 4–8 | P11, P17, P19, P20, P21, P22, P23, P27, P07, P13, P14, P25 | B,C,D |
| P25 Exercise monitoring, incident and support operations | Operations | OPS-02, OPS-04 | 4–8 | P11, P13, P22 | B minimum,C,D |
| P26 Independent engineering onboarding and comprehension | UX | UX-01, UX-02 | 6–12 | P11, P15, P20, P21, P27 | B supervised first session,C independent |
| P27 Close data rights, software IP and customer legal scope | Governance | GOV-01, GOV-02, GOV-03 | 8–16 | P01 | B for pilot,C,D,E |
| P28 Implement approved subscription catalog and payment lifecycle | Commercial | COM-01 | 12–24 | P19, P24, P26, P27 | D |
| P29 Enforce transactional entitlements and quotas | Commercial | COM-02 | 7–14 | P09, P28 | D |
| P30 Qualify organization seats and billing administration | Commercial | COM-03 | 5–10 | P11, P28, P29 | D |
| P31 Exercise support, portability and paid onboarding lifecycle | Commercial | COM-04 | 5–10 | P22, P25, P26, P28, P29, P30 | D |
| P32 Prepare evidence-backed diligence and customer-value record | Governance | GOV-05 | 4–8 | P19, P23, P26, P27 | E |
| P33 Incrementally reduce orchestration duplication | Canonical | ARC-01 | 12–24 | P15, P16, P18, P20 | Post-beta unless required by confirmed fix |
| P34 Qualify advertised exports and restrict unsupported formats | Engineering | EXP-01, EXP-02, EXP-03 | 8–16 | P02, P14, P15, P18, P20 | B advertised scope,C,E |
| P35 Qualify AI semantic safety and evidence preservation | Engineering | AI-01 | 8–16 | P03, P09, P12, P15, P27 | B if AI enabled,C,E |
| P36 Measure real AI/imagery and optional learning qualification | Engineering | AI-02, AI-03 | 6–12 | P12, P23, P27, P35 | C for advertised imagery; optional after launch learning |

## Per-package implementation contracts

The common execution contract is inherited by every numbered field below. Domain-specific details in sibling plans are additional binding acceptance requirements.

### P01 — Preserve audit cases and immutable release evidence

1. **Goal / problem:** Preserve audit cases and immutable release evidence. Issues: TEST-01, TEST-07, TEST-08; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `docs/release/`; `tests/remediation/test_oct15_audit.py (new)`; `apps/web/playwright.full-audit.config.ts`; `backend/application/production_env_validator_v1.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** Read-only baseline; no upstream package. 
5. **Allowed implementation / underlying-cause repair:** Create a new evidence namespace and append-only manifest; reconstruct 24 named assertions without executing engines in unapproved environments; never edit original reports. Capture source/dependency/config fingerprints and explain artifact mismatch.
6. **Alternatives / decision:** Use an append-only managed artifact store later; local immutable manifests suffice initially.
7. **Required regression tests:** Unit: manifest mismatch, duplicate run ID and tampered report rejection; static count/ID reconciliation; later authorized reconstructed suite.
8. **Independent expected results / acceptance:** 24 original cases mapped with provenance and independently expected outcomes; 10 historical failures retained; initial expected failures cannot count as release acceptance; new runs use unique output paths and nonzero failing assertion exit codes. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p01.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Recording secrets or accidentally relabelling reconstructed evidence as original.
11. **Rollback / recovery:** Revert only new harness/docs in implementation branch; retain all evidence already written.
12. **Review / deliverable / completion:** QA lead + release engineer; 3–5 engineer-days; gates A,B,C,D,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P02 — Approve model, numerical and surface decisions

1. **Goal / problem:** Approve model, numerical and surface decisions. Issues: CAN-01; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/canonical_project.py`; `canonical_record.py`; `canonical_canvas.py`; `engines/surface_engine.py`; `apps/web/app/utils/canonicalCanvasProject.ts`; `docs/remediation/`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Write approved ADRs for authoritative representations, result failures, unit/datum metadata, node/cell/TIN conventions and migration policy before semantic changes. Inventory roundtrip contracts; do not replace schema v1 blindly.
6. **Alternatives / decision:** Retain explicit distinct node and cell surface types rather than force all rasters into nodes.
7. **Required regression tests:** Contract snapshots for v1/legacy documents and unsupported future versions; no calculation changes in this decision package.
8. **Independent expected results / acceptance:** Named architect and PE approve numerical/sampling decisions; owner matrix and legacy ambiguity rules published; no unknown unit/datum becomes assumed feet; migration fixtures selected. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p02.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Premature schema lock-in, silently treating old arrays as nodes.
11. **Rollback / recovery:** Docs/contract-only revert; preserve baseline fixtures.
12. **Review / deliverable / completion:** Principal architect + PE; 4–7 engineer-days; gates A,B,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P03 — Repair hydrology result contract and invalid-input handling

1. **Goal / problem:** Repair hydrology result contract and invalid-input handling. Issues: ENG-01, ENG-02; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `engines/hydrology_engine.py`; `backend/planning/runtime.py`; `planner.py`; `backend/application/job_workflows.py`; `backend/planning/hydrology_stage_runners.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01, P02 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Use authoritative total_runoff_cfs and explicit missing-result failure, not getattr zero. Recommend typed internal input errors translated to structured boundary failures; preserve valid zeros. Trace C/I and peak consumers, version changed engine results and label unsourced Tc/rainfall assumptions.
6. **Alternatives / decision:** Structured engine failure results instead of exceptions if all callers can consistently handle them; decide in P02.
7. **Required regression tests:** New hydrology contract/domain/imperial-metric/adapter/integration tests plus existing real-math and relevant job tests; distinguish no catchment from valid zero.
8. **Independent expected results / acceptance:** One-acre C=.625 I=4 gives 2.52 cfs through real helper and affected job/planner paths; invalid/nonfinite/missing inputs never success; explicit empty/zero semantics approved; no invented rainfall/Tc becomes verified. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p03.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Changing defaults may expose formerly hidden failures and alter downstream sizing.
11. **Rollback / recovery:** Roll back reader-compatible code only; retain new result versions/history; mark affected old results unverified and do not reactivate unsafe calculations.
12. **Review / deliverable / completion:** PE + senior backend reviewer; 4–8 engineer-days; gates A,B. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P04 — Unify detention volume, curves and conservative routing

1. **Goal / problem:** Unify detention volume, curves and conservative routing. Issues: ENG-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `engines/detention_engine.py`; `backend/planning/hydrology_stage_runners.py`; `tests/test_real_math_big_pass.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P03 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Use one approved integrated stage-volume function for rectangular geometry and curve increments. Define monotone discharge/initial storage/time units; solve routing with explicit residual/error reporting, bounded timestep and supported overtopping behavior.
6. **Alternatives / decision:** Explicitly exclude overflow/backwater routing from beta rather than invent a broadly capable solver.
7. **Required regression tests:** Analytic prism/square/unequal/tapered cases; terminal partial stage; zero outlet/inflow; nonmonotone times/curves; empty/nonfinite inputs; overflow and drawdown; h,h/2,h/4.
8. **Independent expected results / acceptance:** 100x20x5,4:1 volume 24666.666667 ft3; direct and final curve volume agree within registered tolerance; square/unequal basins pass; no clamped water level hides excess storage; mass balance and step-halving convergence pass reviewed thresholds. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p04.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Changed storage can change recommended geometry and existing alternatives; routing scope may need restriction.
11. **Rollback / recovery:** Keep old results read-only with method/version tags; disable affected exports during rollback; never rewrite historical numeric values.
12. **Review / deliverable / completion:** Hydrology PE + numerical reviewer; 6–12 engineer-days; gates A,B. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P05 — Introduce explicit surface compatibility and registration

1. **Goal / problem:** Introduce explicit surface compatibility and registration. Issues: ENG-05; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `engines/surface_engine.py`; `engines/earthwork_engine.py`; `backend/planning/civil_surface_model.py`; `backend/planning/existing_conditions_importers.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Define metadata-bearing comparison inputs with CRS, XY/Z units, datum, origin, bounds, spacing, affine orientation and sampling semantics. Reject unknown/mismatched alignment; resampling is a separate explicit, sourced operation with error budget.
6. **Alternatives / decision:** Reject incompatible grids in beta; postpone resampling until independently qualified.
7. **Required regression tests:** Translated/rotated grids, differing resolutions, survey feet/international feet, metric, vertical offsets/datums, affine/NoData/bounds mismatch; resampling analytic-plane preservation.
8. **Independent expected results / acceptance:** 1000-ft displaced grids rejected with field-level reasons; equivalent known units can convert explicitly; unknown datum/rotation/NoData cannot be silently aligned; legacy files remain loadable as unverified. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p05.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Rejecting formerly accepted comparisons; metadata migration ambiguity.
11. **Rollback / recovery:** Additive adapter rollback keeps original metadata and arrays; never relabel coordinates or reverse conversions implicitly.
12. **Review / deliverable / completion:** Geospatial engineer + PE; 5–10 engineer-days; gates A,B. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P06 — Correct grid/TIN earthwork integration and factor order

1. **Goal / problem:** Correct grid/TIN earthwork integration and factor order. Issues: ENG-04; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `engines/earthwork_engine.py`; `engines/grading_engine.py`; `engines/surface_engine.py`; `backend/planning/civil_surface_model.py`; `tests/test_real_math_big_pass.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P05 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Implement approved cell-domain integration for node surfaces and explicit cell footprints for rasters; clip partial cells and integrate sign-changing cut/fill separately. Use one shared verified integration path; define strip/shrink/swell order and report raw vs adjusted volumes.
6. **Alternatives / decision:** TIN-based integration for supported triangulated surfaces, node bilinear integration for grids; avoid multiplying legacy totals.
7. **Required regression tests:** Flat/tilted/wedge/two-triangle surfaces; irregular boundary/holes/partial cells; nulls; resolution sequences; m3/ft3/yd3; shrink/swell/strip factors; old fixtures explicitly annotated rather than changed to observed answers.
8. **Independent expected results / acceptance:** 3x3 nodes over 20x20ft raised1ft =400ft3; planar slopes, sign changes and clipped domains satisfy analytic conservation and resolution convergence; node/cell/TIN equivalents agree within PE-approved budget. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p06.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Material changes to grading, quantities and costs; boundary conventions affect persisted surfaces.
11. **Rollback / recovery:** Preserve source surfaces and prior results; version new engine and recompute explicitly; rollback blocks new-method exports if reader incompatible.
12. **Review / deliverable / completion:** PE + numerical/geospatial reviewer; 8–16 engineer-days; gates A,B. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P07 — Constrain GIS and other outbound network requests

1. **Goal / problem:** Constrain GIS and other outbound network requests. Issues: SEC-01; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/planning/gis_provider_registry.py`; `backend/planning/existing_conditions_online.py`; `backend/application/file_workflows.py`; `backend/api/app.py`; `backend/scripts/imagery_detection_gateway.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Centralize outbound policy: approved HTTPS destinations, validated resolved public addresses, revalidated redirects and connected peer, byte/time/concurrency caps; reject credentials/alternate encodings and unsafe schemes. Plan network egress restrictions without buying services.
6. **Alternatives / decision:** Strict curated provider IDs rather than arbitrary custom URLs for beta; network egress enforcement as defense in depth.
7. **Required regression tests:** Fake resolver/transport tests, redirect chains, slow/oversized/compressed responses, userinfo/IDN/IP encodings and provider regressions. No live exploit.
8. **Independent expected results / acceptance:** Loopback/private/link-local/metadata/IPv6/rebinding/redirect cases denied before connection; approved current GIS providers still work with mocks; owner-configured private providers require explicit isolated deployment exception. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p07.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Breaking legitimate GIS hosts, TOCTOU between DNS validation and connect, proxy route bypass.
11. **Rollback / recovery:** Rollback policy code only with affected endpoint disabled; never reopen arbitrary URL access.
12. **Review / deliverable / completion:** Application security reviewer + GIS maintainer; 4–8 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P08 — Stable authentication and distributed abuse controls

1. **Goal / problem:** Stable authentication and distributed abuse controls. Issues: SEC-02, SEC-06; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/api/app.py`; `start_backend_api.sh`; `backend/services/auth_store.py`; `.github/workflows/`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Use independent trusted-source and normalized-account limits; invalid bearer headers never change login buckets. Choose shared atomic TTL-backed counters or managed edge limits plus application controls; trust forwarding only from explicit proxies. Bound keys, log redacted events, avoid permanent lockouts.
6. **Alternatives / decision:** Existing edge provider limits plus durable application account counters; do not assume an unpurchased Redis service.
7. **Required regression tests:** Mock clock/proxy identities, concurrent workers, malformed auth, IPv6/NAT, account-target distribution, counter outage/fail-closed expensive actions, Retry-After and non-enumerating responses.
8. **Independent expected results / acceptance:** Rotating arbitrary bearer/XFF headers cannot evade source/account limits; multiple instances enforce aggregate policy; TTL/cardinality bounded; legitimate shared-IP users and recovery tested; outage behavior documented. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p08.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Overblocking NAT users; shared-counter dependency failure; account lockout abuse.
11. **Rollback / recovery:** Feature-controlled limiter transition and monitored fallback with equal/better abuse protection; no disable-all rollback.
12. **Review / deliverable / completion:** Security reviewer + platform engineer; 6–12 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P09 — Make design writes conflict-safe across every writer

1. **Goal / problem:** Make design writes conflict-safe across every writer. Issues: CAN-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/project_store.py`; `backend/services/project_revision.py`; `backend/application/project_snapshot.py`; `backend/application/chat_workflows.py`; `backend/application/job_workflows.py`; `backend/application/source_context_workflows.py`; `backend/application/plan_pdf_workflows.py`; `apps/web/app/hooks/useDashboardProjectSave.ts`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01, P02 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Inventory direct SQL and every read-modify-write. Require CAS for design aggregates, atomic field-owned updates for metadata and independent collaboration rows, locked input/result checks for results. Preserve existing revision-aware wrapper and archive changed-input calculations; do not blanket-retry stale full snapshots.
6. **Alternatives / decision:** Separate metadata revisions/atomic patches rather than mandatory whole-document conflicts for every timestamp.
7. **Required regression tests:** Barrier-controlled UI/job/chat/import races, permission revocation, retry/duplicate commands, interrupted transactions, copy/replace recovery, metadata/result coexistence and branch history.
8. **Independent expected results / acceptance:** Two edits yield one accepted revision and an explicit recoverable conflict; delayed chat/AI/job cannot overwrite newer geometry; comments/presence do not invalidate unrelated edits; SQLite and PostgreSQL atomicity tested. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p09.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Deadlocks, conflict storms, broken legacy writers, lost history or tenant authorization.
11. **Rollback / recovery:** Expand/contract writer rollout; preserve recovery snapshots; disable unsafe writers if reverting; no destructive schema rollback.
12. **Review / deliverable / completion:** Senior backend/data-integrity reviewer; 8–16 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P10 — Migrate session storage, expiry and revocation safely

1. **Goal / problem:** Migrate session storage, expiry and revocation safely. Issues: SEC-04; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/auth_store.py`; `backend/services/database.py`; `backend/api/app.py`; `apps/web/app/utils/auth.ts`; `apps/web/lib/api.ts`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01, P02 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Store keyed/token digests or secure hashes of random tokens with explicit idle/absolute expiry and revocation. Decide bearer-vs-cookie boundary with P13; use additive migration, bounded legacy exchange or deliberate reauthentication; never retain indefinite raw-token fallback.
6. **Alternatives / decision:** Retain short-lived bearer sessions initially rather than combine a cookie architecture migration with hash/expiry fix.
7. **Required regression tests:** Clock-boundary/rotation-replay/session-fixation/logout races; legacy migration and roll-forward; no token in URLs/logs/files; unauthenticated endpoints unaffected.
8. **Independent expected results / acceptance:** DB read no longer yields usable new sessions; expiry/logout/all-device revocation/rotation enforced; concurrent tabs/devices behave per policy; old records never become permanent bypass; login failure reveals no identity. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p10.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Unexpected logout, migration incompatibility, CSRF if cookies introduced.
11. **Rollback / recovery:** Prefer forced reauthentication/roll-forward over restoring raw long-lived credentials; keep additive columns until compatibility proved.
12. **Review / deliverable / completion:** Security reviewer + backend lead; 5–10 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P11 — Verify enrollment, invitations and organization identity

1. **Goal / problem:** Verify enrollment, invitations and organization identity. Issues: SEC-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/auth_store.py`; `backend/services/project_store.py`; `backend/services/database.py`; `backend/api/app.py`; `apps/web/app/components/ProjectTeamMemoryPanel.tsx`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P08, P10 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Adopt verified operator provisioning for free beta without purchased mail; design hashed, expiring single-use invite/verification tokens. Existing accounts need ownership proof before grants; enforce creator-only grants, revocation and organization boundaries.
6. **Alternatives / decision:** Operator-verified account provisioning for beta; provider-backed email delivery later after explicit approval.
7. **Required regression tests:** Victim/pre-registration, email-change, token replay, concurrent acceptance, seat/member revocation, last-owner and unauthorized organization grants; rate-limited enumeration-safe responses.
8. **Independent expected results / acceptance:** Attacker pre-registering victim email cannot obtain invitation; pending membership confers no access; expired/replayed/revoked tokens fail; closed enrollment fails even with empty DB; existing authorized users can sign in. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p11.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Locking out approved pilot users; accidentally granting pending invitations; outbound mail cost.
11. **Rollback / recovery:** Restore access only by audited identity verification; no fallback to unverified email grants.
12. **Review / deliverable / completion:** Security + product owner; 6–12 engineer-days; gates B,C,D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P12 — Enforce consent at learning collection and lifecycle boundaries

1. **Goal / problem:** Enforce consent at learning collection and lifecycle boundaries. Issues: SEC-05; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/chat_learning_store.py`; `backend/services/chat_learning_pipeline.py`; `backend/services/project_store.py`; `backend/application/chat_workflows.py`; `backend/services/data_lifecycle.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P09, P11 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Require validated user/org purpose-scoped consent before logging, deny unknown context; redact/minimize, separate operational logs from training, define TTL/deletion and dataset lineage. Keep collection disabled until all gates pass.
6. **Alternatives / decision:** Keep learning entirely out of beta/public initial scope.
7. **Required regression tests:** All consent combinations, absent actor, delayed task after revocation, export/delete, redaction and concurrent append tests; synthetic data only.
8. **Independent expected results / acceptance:** Global flag alone cannot collect opted-out records; org prohibition overrides personal opt-in; withdrawal stops collection and propagates approved deletion; no sensitive raw geometry/prompts in training without purpose rights. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p12.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Deleting reproducibility evidence improperly; missed downstream dataset copies.
11. **Rollback / recovery:** Global collection off is safe rollback; preserve legally required minimal audit events per approved retention policy.
12. **Review / deliverable / completion:** Privacy/security reviewer + counsel for policy; 4–8 engineer-days; gates B if enabled; C,D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P13 — Harden operator diagnostics and browser trust boundary

1. **Goal / problem:** Harden operator diagnostics and browser trust boundary. Issues: SEC-07, SEC-09; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/api/app.py`; `backend/application/production_env_validator_v1.py`; `apps/web/next.config.ts`; `apps/web/app/layout.tsx`; `apps/web/app/utils/auth.ts`; `apps/web/lib/api.ts`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P10 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Create least-privilege operator authorization and redacted diagnostics. Design CSP in report-only then enforce after testing maps/workers/Three/fonts; decide cookie CSRF/origin protection or bearer threat model, sanitize rendered files/HTML, review third-party scripts.
6. **Alternatives / decision:** Keep bearer approach with tight CSP until a separately reviewed cookie migration.
7. **Required regression tests:** Role negatives, XSS sinks and SVG/PDF rendering, CSP violations, frame protections, token theft exposure, cross-origin/CSRF and third-party failure tests.
8. **Independent expected results / acceptance:** Ordinary users cannot access operator payloads; no secrets in diagnostics; malicious script/file fixtures blocked; required map/render workflows operate under CSP; cookie choice has SameSite/Secure/HttpOnly and CSRF tests. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p13.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Breaking Mapbox/worker assets; assuming CSP alone fixes XSS; CSRF regression.
11. **Rollback / recovery:** Revert to monitored report-only CSP temporarily with documented exception, never restore public diagnostics; revoke exposed sessions.
12. **Review / deliverable / completion:** Security reviewer + frontend lead; 5–10 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P14 — Make uploaded sources immutable and failure-safe

1. **Goal / problem:** Make uploaded sources immutable and failure-safe. Issues: SEC-08; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/application/file_workflows.py`; `backend/services/artifact_service.py`; `backend/services/data_lifecycle.py`; `backend/services/brief_sources.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P09 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Allocate opaque immutable IDs, stream to unique temp files with byte limits/hash, atomically publish successful content; preserve original display name and original hash; cleanup only task-owned temp objects. Add ownership, parser resource and retention checks.
6. **Alternatives / decision:** Content-addressed bytes with per-tenant references; avoid cross-tenant hash-existence disclosure.
7. **Required regression tests:** Collision/failure injection, interrupted stream, dedup collision authorization, zip/image bomb parser bounds, immutable provenance, export/delete and orphan reconciliation.
8. **Independent expected results / acceptance:** Same filename reupload creates distinct source/version; failed oversized/interrupted upload leaves old source byte-identical; hash verified on use/export; no cross-tenant path or symlink access. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p14.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Breaking old image URLs/references; orphaned files; over-eager cleanup.
11. **Rollback / recovery:** Maintain legacy read adapter and source mapping; restore quarantined task-owned files; never overwrite originals.
12. **Review / deliverable / completion:** Security + storage reviewer; 4–8 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P15 — Verify explicit engineering dependency/change contracts

1. **Goal / problem:** Verify explicit engineering dependency/change contracts. Issues: CAN-02; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/dependency_graph.py`; `backend/planning/reactive_model.py`; `apps/web/app/utils/dependencyGraph.ts`; `canonicalDependencyPolicies.ts`; `backend/services/canonical_results.py`; `backend/application/artifact_workflows.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P03, P05, P06, P09 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Add declared owner/read-set/write-set dependency versions. Lightweight geometry updates can run live; heavy reruns need impact preview/consent. Invalidate quantity/cost/dimensions/exports and preserve old review records by revision, not label them current.
6. **Alternatives / decision:** Conservative full downstream invalidation first, then justify finer incremental reuse.
7. **Required regression tests:** Table-driven perturbation/mutation tests; undo/redo and branch recovery; partial rerun vs full-run equivalence on supported deterministic fixtures; export race checks.
8. **Independent expected results / acceptance:** Road/building/utility/elevation/surface edits match expected dirty closure; no missing downstream result becomes fresh; cycles and unsupported relationships fail; unchanged results retained with proof; failed rerun never publishes current. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p15.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Over-invalidation, under-invalidation, hidden cycles and excessive heavy jobs.
11. **Rollback / recovery:** Keep prior graph/engine versions with explicit stale states; disable unqualified propagation instead of claiming freshness.
12. **Review / deliverable / completion:** Architect + relevant discipline PE; 8–16 engineer-days; gates A(scope),B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P16 — Separate editable data, execution state and archival growth

1. **Goal / problem:** Separate editable data, execution state and archival growth. Issues: CAN-04; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/canonical_record.py`; `backend/application/job_workflows.py`; `backend/services/project_store.py`; `apps/web/app/utils/canonicalCanvasProject.ts`; `apps/web/app/utils/editTransactions.ts`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P09, P15 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Reference immutable result/checkpoint records by ID/hash instead of embedding recursive snapshots; bound active history and archive with checksums; incremental scoped writes where safe. Provide lossless legacy hydration/export before removing duplicate fields.
6. **Alternatives / decision:** Compression as temporary mitigation only; not a substitute for ownership and reference fixes.
7. **Required regression tests:** Large synthetic fixtures, before/after serialized bytes/RSS, deep-copy regression, reference GC/retention, rollback readers and migration idempotence.
8. **Independent expected results / acceptance:** 100 repeated edit/apply/save cycles stay within documented source-size amplification target; every result reproduces its input; old projects migrate without ID/history/source loss; archive and failure recovery verified. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p16.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Dangling references, broken old clients, garbage collection losing evidence.
11. **Rollback / recovery:** Dual-read, single-write expand/contract migration; retain original snapshot backups; reference GC disabled until tested.
12. **Review / deliverable / completion:** Architect + data/platform reviewer; 8–16 engineer-days; gates B,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P17 — Qualify software supply chain and dependency exposure

1. **Goal / problem:** Qualify software supply chain and dependency exposure. Issues: SEC-11; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `requirements_backend.txt`; `requirements_test.txt`; `apps/web/package-lock.json`; `Dockerfile`; `Dockerfile.backend`; `.github/workflows/`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Inventory runtime/dev/transitive/container/actions SBOM; use authorized fresh scans, evaluate reachability/exploitability and safe upgrades; pin build provenance/actions; document time-limited exceptions. No scan/install executed in planning.
6. **Alternatives / decision:** Document non-exploitable temporary exceptions with independent approval, not permanent suppression.
7. **Required regression tests:** Advisory fixture parsing, lockfile integrity, upgrade regression groups, container non-root/read-only/volume checks and action permissions.
8. **Independent expected results / acceptance:** Frozen candidate has current scan set, zero unresolved reachable High/Critical exposures for scope; each other advisory has owner/expiry/rationale; clean-room dependency/build provenance matches manifest. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p17.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Incompatible forced downgrades or ignored dev/build compromise paths.
11. **Rollback / recovery:** Rollback lockfile/image only to reviewed non-vulnerable supported version; no blanket audit fix.
12. **Review / deliverable / completion:** Security + release engineer; 4–8 engineer-days; gates B,C,D,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P18 — Build independent engine-family qualification packs

1. **Goal / problem:** Build independent engine-family qualification packs. Issues: ENG-06, TEST-02; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `engines/`; `backend/planning/`; `core/`; `backend/fixtures/golden/`; `tests/`; `docs/remediation/CIVORA_ENGINEERING_VALIDATION_PLAN.md`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P03, P04, P05, P06, P15 accepted for required scope. Must first split into explicitly scoped <=10-day children with independent review.
5. **Allowed implementation / underlying-cause repair:** Execute the engine-by-engine matrix in validation plan; split by discipline into <=10-day child packages, independent expected values authored before observed outputs. Qualify only declared supported claims; discovered fixes require new scoped tickets.
6. **Alternatives / decision:** Qualify narrow commercial site workflow first; defer bridge/structural/vent analysis claims rather than implement entire disciplines.
7. **Required regression tests:** Analytic and reference-software cases per family, pathology/property/metamorphic cases, unit/datum conversions, independent data and connected quantity/export traces.
8. **Independent expected results / acceptance:** Every enabled engine has versioned assumptions/standards/oracles/tolerances/negative/unit/conservation tests and review disposition; no unqualified capability advertised as engineered; no self-oracle-only acceptance. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p18.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Scope explosion; unsupported engineering promises; hidden defects beyond initial five.
11. **Rollback / recovery:** Restrict or disable unqualified workflows; keep old outputs accessible as historical/unverified; no automatic bulk re-engineering.
12. **Review / deliverable / completion:** Discipline PE(s), geospatial/numerical expert; QA evidence custodian; 75–150 engineer-days; gates A per scope,B,C,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P19 — Obtain independent scope-specific professional acceptance

1. **Goal / problem:** Obtain independent scope-specific professional acceptance. Issues: GOV-04; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `docs/release/rc1-engineer-uat-packet.md`; `backend/application/commercial_site_benchmark.py`; `core/professional_release.py`; `new private review evidence (outside public repo)`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P18, P20, P27, P34 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Engage independent appropriately licensed engineers; freeze supported scope, input rights and exact candidate; use blinded independently prepared calculations and attributable discrepancy review. No automated agent signs approval.
6. **Alternatives / decision:** Use multiple discipline reviewers when one PE cannot competently cover scope.
7. **Required regression tests:** Evidence completeness/hash/revision rejection, stale review invalidation and independent replay of calculations/exports.
8. **Independent expected results / acceptance:** All supported beta disciplines have signed attributable acceptance tied to input hashes/release; limitations explicit; no unresolved high-severity supported-workflow defect; no construction/stamp authority inferred. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p19.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Reviewer availability, scope misunderstanding and exposing confidential evidence.
11. **Rollback / recovery:** Withdraw release recommendation and return affected workflows to unverified; retain signed history.
12. **Review / deliverable / completion:** Independent PE(s) + product/release owner; 6–12 engineer-days; gates B,C,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P20 — Complete positive and negative connected engineering journeys

1. **Goal / problem:** Complete positive and negative connected engineering journeys. Issues: TEST-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `apps/web/tests/live/`; `tests/test_real_firm_end_state_workflow.py`; `backend/application/commercial_site_benchmark.py`; `backend/application/artifact_workflows.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P03, P04, P05, P06, P09, P14, P15, P16, P18 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Run real isolated API/UI workflows using reviewed fixture inputs through import/edit/calculate/history/quantity/cost/report/export. Distinguish mocked provider layers from actual backend paths. Preserve every error path and result scope.
6. **Alternatives / decision:** Use fully offline recorded provider responses plus separate authorized real-provider qualification.
7. **Required regression tests:** Full 12-step journey, provider outage, permission revoke, stale exports, failed job, cancel/retry, undo branches, import uncertainty; template/duplicate/group workflows included.
8. **Independent expected results / acceptance:** At least small commercial and constrained infill fixtures complete supported calculated deliverables; save/reopen and edits preserve IDs/history; negative unsafe inputs block exports; no hidden stage failure accepted by success wrapper. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p20.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Tests accepting empty success mocks, false-ready wrappers or stale result reuse.
11. **Rollback / recovery:** Test-only rollback never deletes prior failures; failures create blocking tickets, not relaxed assertions.
12. **Review / deliverable / completion:** QA lead + backend/frontend owners + PE for expected outputs; 10–20 engineer-days; gates B,C,D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P21 — Stabilize supported-browser/accessibility acceptance

1. **Goal / problem:** Stabilize supported-browser/accessibility acceptance. Issues: TEST-04, UX-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `apps/web/tests/live/`; `apps/web/playwright.config.ts`; `apps/web/playwright.full-audit.config.ts`; `apps/web/app/components/`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P09, P15, P20 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Triage every historical failed/skipped case by product/test/environment/flake/unsupported status; define supported desktop/touch/browser matrix. Use representative stages and keyboard/screen-reader tasks, not only shell scans.
6. **Alternatives / decision:** Narrow supported-browser beta policy explicitly, not implicit universal support.
7. **Required regression tests:** Chromium/WebKit/Firefox where supported, 320px/touch, keyboard/focus/zoom, labels, warnings, dialogs, map controls and dense project timing.
8. **Independent expected results / acceptance:** Two consecutive full supported-matrix candidate runs pass with original failures accounted; no serious/critical accessibility violations on primary tasks; Firefox either proven or explicitly not advertised, never silently skipped. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p21.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** False green through skipping, retry masking and flaky selectors.
11. **Rollback / recovery:** Retain original artifacts and failure dispositions; revert UI changes only with same accessibility protections.
12. **Review / deliverable / completion:** QA/accessibility specialist + frontend lead; 6–12 engineer-days; gates B scoped,C. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P22 — Qualify recovery, migrations and reversible deployment

1. **Goal / problem:** Qualify recovery, migrations and reversible deployment. Issues: TEST-05, OPS-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/database.py`; `backup_restore.py`; `data_lifecycle.py`; `job_queue.py`; `Dockerfile.backend`; `docs/release/rc1-hosted-backup-restore-evidence.md`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P09, P10, P14, P16, P01 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Plan approved isolated restores of DB plus artifacts; verify schema/model/job/reference integrity, encryption/access and retention; exercise expand/contract migration, concurrent start, interruption and rollback/roll-forward with test data.
6. **Alternatives / decision:** Operator-controlled pilot restore with narrow guarantees before automated multi-region disaster recovery.
7. **Required regression tests:** Backup failure/corruption/missing file, token revocation after restore, partially migrated DB, duplicate worker claim, orphaned artifact and disaster runbook rehearsal.
8. **Independent expected results / acceptance:** Measured RPO/RTO meet approved target; canonical/file checksums and logical counts match; no duplicate job side effects; old/new compatibility proved or rollback requires restore. Historical August drill remains unchanged. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p22.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Restoring old tokens/access or losing post-backup edits; destructively testing production.
11. **Rollback / recovery:** Restore only new isolated environment; preserve original; forward-only repair unless rehearsed restore is explicitly approved.
12. **Review / deliverable / completion:** Platform/DB reviewer + security + release owner; 8–16 engineer-days; gates B,C,D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P23 — Measure operating envelope and unit economics

1. **Goal / problem:** Measure operating envelope and unit economics. Issues: TEST-06; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/application/golden_load_benchmarks.py`; `backend/services/job_queue.py`; `backend/services/database.py`; `apps/web/app/utils/performanceProbes.ts`; `AI providers`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P16, P20, P22 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Use approved S/M/L fixtures and concurrency staircase; collect p50/p95/error/RSS/DB/artifact growth, throughput, provider tokens/cost and actual hosting costs. Paid measurement needs explicit budget; mocks cannot certify costs.
6. **Alternatives / decision:** Reuse existing services and offline timing; mark real provider cost unverified until authorized.
7. **Required regression tests:** Local deterministic performance, approved isolated soak, provider timeouts, overload backpressure and budget guard tests; no production stress.
8. **Independent expected results / acceptance:** Published tested limits and failure behavior; targets in release plan met or scope narrowed; 100-cycle growth/long jobs/queue cancellation bounded; real cost inputs source/date-labelled, no fabricated margins. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p23.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Unrepresentative fixtures and accidental paid/provider or production load.
11. **Rollback / recovery:** Stop load, retain redacted evidence; restore isolated fixtures; enforce lower tested capacity limits.
12. **Review / deliverable / completion:** Platform/performance engineer + product finance owner; 8–16 engineer-days; gates B scoped,C,D,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P24 — Verify exact hosted candidate and controlled enrollment

1. **Goal / problem:** Verify exact hosted candidate and controlled enrollment. Issues: OPS-01; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `railway.toml`; `Dockerfile*`; `apps/web/app/api/release-identity/route.ts`; `backend/api/app.py`; `docs/release/hosted-canary.md`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P11, P17, P19, P20, P21, P22, P23, P27, P07, P13, P14, P25 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Only after explicit deployment/access authorization, use existing hosting, record identities/config digest/enrollment/rollback and isolated test-account permissions. No new purchase or deployment implied by this plan.
6. **Alternatives / decision:** Keep offline qualification and defer hosted gate if no authorized safe environment.
7. **Required regression tests:** Authenticated canary, deployment skew, closed signup, minimum role, job retry and artifact ownership with permitted synthetic accounts.
8. **Independent expected results / acceptance:** Approved target serves exact candidate/API/worker versions; signup closed and approved account works; tenant/save/job/artifact checks pass; backup and rollback evidence current. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p24.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Version skew, customer mutation, secrets in evidence and unsafe rollback.
11. **Rollback / recovery:** Rehearsed prior image/config restore or roll-forward; suspend enrollment if integrity uncertain.
12. **Review / deliverable / completion:** Release/platform owner + security; founder authorizes deployment; 4–8 engineer-days; gates B,C,D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P25 — Exercise monitoring, incident and support operations

1. **Goal / problem:** Exercise monitoring, incident and support operations. Issues: OPS-02, OPS-04; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/application/memory_logging.py`; `backend/services/support_store.py`; `backend/api/app.py:2441`; `vercel.json`; `docs/release/rc1-incident-runbook.md`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P11, P13, P22 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Assign human on-call/support ownership, redacted observability, escalation and incident drills. Check scheduled job origin/method/auth; leave learning off unless P12/P36 qualify it; verify alerts in existing authorized tooling.
6. **Alternatives / decision:** Manual monitored checklist for small free pilot with explicit staffing commitments.
7. **Required regression tests:** Alert injection in isolation, log redaction, authorization for support operations, queue timeout and retention; no real outreach without permission.
8. **Independent expected results / acceptance:** Synthetic fault reaches responsible person, acknowledgement/escalation recorded; failed jobs, backup failures and auth abuse visible; cron either verified end-to-end or explicitly disabled; monitored contact published. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p25.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Sensitive telemetry, noisy alerts and accidentally starting learning/provider jobs.
11. **Rollback / recovery:** Disable faulty scheduled collection and preserve alert alternatives; runbook rollback with named owner.
12. **Review / deliverable / completion:** Operations/security lead + support owner; 4–8 engineer-days; gates B minimum,C,D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P26 — Independent engineering onboarding and comprehension

1. **Goal / problem:** Independent engineering onboarding and comprehension. Issues: UX-01, UX-02; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `apps/web/app/components/`; `apps/web/app/support/`; `docs/release/rc1-engineer-uat-packet.md`; `docs/help/ (new if approved)`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P11, P15, P20, P21, P27 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Recruit independent engineers with founder permission; use standardized tasks, no coaching during scoring; observe units/source/review/export understanding; only evidence-led UI changes, concise labels and progressive disclosure.
6. **Alternatives / decision:** Moderated supervised beta first; independent usability evidence required before public launch.
7. **Required regression tests:** Tasks account/project/GIS/units/drawing/calc/error/history/undo/export/sharing; assistance/time/error and repeat-session metrics; accessibility review.
8. **Independent expected results / acceptance:** At least 5 independent participants across >=2 firms/teams; zero critical reliance/data errors; >=90% primary task completion, >=80% without help; 100% identify unverified/geometry-only output correctly; small sample limitations recorded. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p26.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Small-sample false confidence, founder coaching, polishing away important warnings.
11. **Rollback / recovery:** Revert confusing UI changes while retaining engineering warnings; narrow release claims.
12. **Review / deliverable / completion:** UX lead + independent engineers + PE for task validity; 6–12 engineer-days; gates B supervised first session,C independent. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P27 — Close data rights, software IP and customer legal scope

1. **Goal / problem:** Close data rights, software IP and customer legal scope. Issues: GOV-01, GOV-02, GOV-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `docs/release/evidence-templates/source-rights-review.json`; `dependency manifests`; `Git contributor history`; `backend/services/brief_sources.py`; `core/professional_release.py`; `customer documents outside public repo`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P01 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Obtain human-authored provider/data/contributor/model license inventory; counsel reviews assignments, terms/privacy/DPA/retention/customer ownership, professional liability/insurance and incident duties; engineers implement approved policies later.
6. **Alternatives / decision:** Narrow rights-cleared customer-upload workflow first; do not wait for every worldwide provider.
7. **Required regression tests:** Evidence completeness and forbidden-source policy tests planned; no automated legal signoff.
8. **Independent expected results / acceptance:** Every enabled source permits intended query/process/display/retain/export; unresolved assets disabled; contributor/model/dependency obligations recorded; approved pilot/customer terms and liability scope with accountable owner. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p27.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Assuming public access or AI generation establishes ownership; publishing confidential agreements.
11. **Rollback / recovery:** Exclude disputed assets/provider/claims; preserve originals and legal holds.
12. **Review / deliverable / completion:** Qualified counsel + relevant PE + founder/IP owner; 8–16 engineer-days; gates B for pilot,C,D,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P28 — Implement approved subscription catalog and payment lifecycle

1. **Goal / problem:** Implement approved subscription catalog and payment lifecycle. Issues: COM-01; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/billing.py`; `backend/api/app.py`; `backend/services/database.py`; `apps/web/app/ (billing UI new)`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P19, P24, P26, P27 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** After safe pilot scope, define proposed $79 Pro/$199 Engineer/$149-seat Teams/custom Enterprise offers; provider-hosted checkout, customer linking, verified signed/idempotent webhooks, lifecycle/reconciliation/admin views. No raw card data.
6. **Alternatives / decision:** Provider payment links/manual free pilot first; subscription claims stay unavailable until qualified.
7. **Required regression tests:** Out-of-order/duplicate/forged webhook, lost event, reconciliation replay, payment failure grace, cancellation effective date and partial refund. Sandbox only.
8. **Independent expected results / acceptance:** Sandbox renewal/failure/cancel/upgrade/downgrade/proration/trial/refund flows pass; tax/refund policies approved by humans; invoices/ledger reconcile; no live charging without separate approval. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p28.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Double charges, incorrect proration, webhook race and identity mismatch.
11. **Rollback / recovery:** Disable new checkout, reconcile provider ledger, preserve webhook events; no blind reversal of charges or deletion of financial records.
12. **Review / deliverable / completion:** Payments/security reviewer + finance/legal product owner; 12–24 engineer-days; gates D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P29 — Enforce transactional entitlements and quotas

1. **Goal / problem:** Enforce transactional entitlements and quotas. Issues: COM-02; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/billing.py`; `backend/api/app.py`; `backend/services/job_queue.py`; `backend/application/job_workflows.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P09, P28 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Use authoritative server entitlements and atomic reservation/finalization/release for jobs/exports/usage; check on enqueue and execution, not UI only; define versioned plans and time windows/grace/read-only preservation.
6. **Alternatives / decision:** Flat bounded included usage initially, avoid complex usage billing until metering reliable.
7. **Required regression tests:** Burst/concurrency/clock/billing-outage/role/retry/idempotency and double-consumption tests; free-pilot exemption explicit and not global bypass.
8. **Independent expected results / acceptance:** Concurrent requests cannot exceed approved quota; upgrade/cancel/refund and webhook delay consistent; failed/cancelled jobs settle correctly; old designs readable/exportable per approved portability policy. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p29.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Locking customers out of their data, charging on retry, asynchronous overspend.
11. **Rollback / recovery:** Freeze new paid work while preserving read/export rights; reconcile reservations before resuming.
12. **Review / deliverable / completion:** Payments/backend lead + security + product; 7–14 engineer-days; gates D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P30 — Qualify organization seats and billing administration

1. **Goal / problem:** Qualify organization seats and billing administration. Issues: COM-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/project_store.py`; `database.py`; `billing.py`; `apps/web/app/components/ProjectTeamMemoryPanel.tsx`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P11, P28, P29 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Separate project permissions from organization/billing roles; verified seat acceptance/removal, scheduled billable changes, last-owner safeguards, admin visibility and audit events.
6. **Alternatives / decision:** Free project sharing for pilot; defer enterprise identity features.
7. **Required regression tests:** Seat race, cross-org grants, last-admin recovery, suspended user, SCIM/SSO explicitly unsupported unless separately implemented.
8. **Independent expected results / acceptance:** Seat count and invoices reconcile under concurrent join/remove; pending invites not billable unless approved; billing admin cannot silently read every project; data access revoked as intended. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p30.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Cross-tenant leakage and inconsistent seat proration.
11. **Rollback / recovery:** Pause seat mutations and reconcile provider/state; never infer permission from paid seat.
12. **Review / deliverable / completion:** Security/payments reviewer + product; 5–10 engineer-days; gates D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P31 — Exercise support, portability and paid onboarding lifecycle

1. **Goal / problem:** Exercise support, portability and paid onboarding lifecycle. Issues: COM-04; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/services/support_store.py`; `backend/services/data_lifecycle.py`; `apps/web/app/support/`; `billing UI`; `customer documentation`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P22, P25, P26, P28, P29, P30 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Run synthetic customer subscription/onboarding/support/export/delete journey; approved retention/legal-hold/backups explained; support access scoped/audited and refund handoffs rehearsed.
6. **Alternatives / decision:** Free pilot support rehearsal before paid lifecycle activation.
7. **Required regression tests:** Cross-tenant export, revoked support access, failed export/delete, quarantine recovery, billing deletion separation and backup-retention notices.
8. **Independent expected results / acceptance:** Customer can subscribe in sandbox, onboard unaided, use supported workflow, receive acknowledged support, export complete owned data and request verified deletion with documented retained exceptions. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p31.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Erasing financial/legal records, missing shared-project ownership and unmonitored support.
11. **Rollback / recovery:** Quarantine and verified restore for permitted test data; legal-hold-aware roll-forward; no unapproved production deletions.
12. **Review / deliverable / completion:** QA + support/privacy/finance owners; 5–10 engineer-days; gates D. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P32 — Prepare evidence-backed diligence and customer-value record

1. **Goal / problem:** Prepare evidence-backed diligence and customer-value record. Issues: GOV-05; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `docs/remediation/`; `investor materials (only upon separate edit authorization)`; `private customer evidence`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P19, P23, P26, P27 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Assemble exact capability matrix, architecture/risk closure and costs; collect permissioned measured time savings/repeat use and purchasing interest without inventing traction; separate prototype/pilot/payments states.
6. **Alternatives / decision:** Fundraise on an honest scoped technical/pilot thesis, not claim public commercial readiness.
7. **Required regression tests:** Dossier links/hashes/capability-vs-gates crosscheck and independent demo replay.
8. **Independent expected results / acceptance:** Gate E dossier reproducible, discrepancies disclosed; IP/rights and risks reviewable; actual interviews/usage labelled with sample/date/method; no valuation inferred from source. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p32.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Marketing overstatement and confidential customer disclosure.
11. **Rollback / recovery:** Withdraw unsupported claims; preserve prior evidence versions.
12. **Review / deliverable / completion:** Independent technical reviewer + founder/finance + customer permission; 4–8 engineer-days; gates E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P33 — Incrementally reduce orchestration duplication

1. **Goal / problem:** Incrementally reduce orchestration duplication. Issues: ARC-01; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `planner.py`; `planner_orchestrator.py`; `backend/api/app.py`; `backend/application/chat_workflows.py`; `apps/web/app/PerformanceAIDashboardView.tsx`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P15, P16, P18, P20 accepted for required scope. Must first split into explicitly scoped <=10-day children with independent review.
5. **Allowed implementation / underlying-cause repair:** After characterization, extract one owned boundary per <=5-day child patch; share contracts and eliminate dead projections only with lossless adapters. Do not change numerical behavior during structural extraction.
6. **Alternatives / decision:** Leave stable large modules intact if extraction risk exceeds maintainability benefit.
7. **Required regression tests:** Characterization snapshots, compatibility/import cycles, shadow comparisons and existing full affected suites.
8. **Independent expected results / acceptance:** Public contract/golden/legacy roundtrips unchanged; smaller modules have explicit ownership and no duplicated calculation source; complexity/load measurements compared. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p33.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Massive merge conflicts, behavior drift hidden in refactor.
11. **Rollback / recovery:** Revert extraction commits independently of numerical fixes; keep adapters until no supported reader needs them.
12. **Review / deliverable / completion:** Principal architect + module maintainer; 12–24 engineer-days; gates Post-beta unless required by confirmed fix. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P34 — Qualify advertised exports and restrict unsupported formats

1. **Goal / problem:** Qualify advertised exports and restrict unsupported formats. Issues: EXP-01, EXP-02, EXP-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `output/dxf_exporter.py`; `backend/planning/landxml_io.py`; `backend/planning/dwg_compatibility.py`; `backend/planning/export_external_verification.py`; `backend/services/artifact_service.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P02, P14, P15, P18, P20 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Verify DXF/PDF/LandXML units/geometry/IDs/elevations/plot scales in independent target tools; reject or disclose LandXML Z=0/feet-only limitations. Native DWG/Civil3D remain excluded unless separately justified, licensed and qualified.
6. **Alternatives / decision:** Offer reviewed DXF/PDF only for beta; defer LandXML/native conversions.
7. **Required regression tests:** External tool roundtrips, metric/imperial headers, dimensions/islands, group/hide/rotation, corrupt/unsupported files, print scale and object/revision hashes.
8. **Independent expected results / acceptance:** Advertised format/version matrix has attributable import/print evidence; no stale/unsafe contents; 2D-only exports cannot masquerade as engineered 3D pipe profiles; native formats truthfully unavailable. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p34.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Breaking existing review exchanges; licensing costs and fabricated 3D elevations.
11. **Rollback / recovery:** Retain supported older review format with limitations; never synthesize absent elevations to pass import.
12. **Review / deliverable / completion:** Independent CAD technician + PE + export maintainer; 8–16 engineer-days; gates B advertised scope,C,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P35 — Qualify AI semantic safety and evidence preservation

1. **Goal / problem:** Qualify AI semantic safety and evidence preservation. Issues: AI-01; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `parsers/ai_parser.py`; `backend/application/chat_workflows.py`; `backend/planning/ai_orchestration_evidence.py`; `apps/web/app/hooks/useDashboardChatSendHandlers.ts`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P03, P09, P12, P15, P27 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Separate trusted commands from untrusted retrieved/imported text; typed allowlist intents, preconditions/units/source claims, user confirmation for destructive or heavy actions; user accepted assumptions remain assumptions, not observed facts.
6. **Alternatives / decision:** Beta AI suggestion-only until mutating commands independently qualify.
7. **Required regression tests:** Versioned synthetic evaluation corpus, malformed JSON, prompt injection, false citations/units, delayed revisions, hidden edits and disabled provider deterministic paths.
8. **Independent expected results / acceptance:** Adversarial prompts/documents cannot elevate role, invent verified utilities/elevations or activate stale results; ambiguity asks targeted questions; valid supported commands retain usability and fail safely on provider errors. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p35.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. 
10. **Risks / side effects:** Overblocking valid commands, treating schema validation as factual truth.
11. **Rollback / recovery:** Disable mutating AI intents, retain read-only/explicit structured workflows; preserve audit trail.
12. **Review / deliverable / completion:** Security reviewer + PE + AI/backend lead; 8–16 engineer-days; gates B if AI enabled,C,E. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

### P36 — Measure real AI/imagery and optional learning qualification

1. **Goal / problem:** Measure real AI/imagery and optional learning qualification. Issues: AI-02, AI-03; original finding/evidence/root cause are recorded individually in the issue register.
2. **Target files:** `backend/ai/provider.py`; `image_provider.py`; `backend/application/ai_visualization_workflows.py`; `backend/services/chat_learning_pipeline.py`; `backend/planning/vision_shadow_evaluation.py`.
3. **Out of scope:** common exclusions; no behavior beyond linked issue scope. Numerical outputs cannot change without approved method/version/tolerance decisions; commercial activation never implied.
4. **Preconditions / order:** P12, P23, P27, P35 accepted for required scope. 
5. **Allowed implementation / underlying-cause repair:** Under separate provider/spend approval, measure visual footprint fidelity, numerical hallucinations, latency/cost and error recovery. Learning requires rights-cleared datasets, train/test isolation, drift and signed promotion review; keep visuals nonengineering.
6. **Alternatives / decision:** Keep optional imagery/learning unavailable without blocking deterministic core release.
7. **Required regression tests:** Provider timeout/budget/retry/version drift, geometry overlay metrics, privacy deletion, held-out leakage and promotion rollback.
8. **Independent expected results / acceptance:** Real-provider samples meet preapproved task-specific metrics and budgets; mock/real evidence separated; no imagery changes canonical geometry; learning remains off absent consent and held-out acceptance. Domain numerical values require independent oracle and PE-approved tolerance before observations.
9. **Verification commands:** common pNN pytest template with `test_p36.py`; select reviewed existing affected tests; frontend commands only for listed frontend paths. External/human/provider evidence cannot be replaced by a local command or fabricated fixture; obtain separate authorization.
10. **Risks / side effects:** Paid calls, data leakage and unrepresentative pretty images.
11. **Rollback / recovery:** Disable provider/learning, revert model to last qualified version; preserve original sources and model evidence.
12. **Review / deliverable / completion:** AI/security/privacy lead + PE for claims; founder approves spend; 6–12 engineer-days; gates C for advertised imagery; optional after launch learning. Record method/ownership/API decisions, runbook/compatibility changes and common completion report. Documentation deliverable: package-specific evidence manifest plus updates to relevant domain plan, not overwritten audit history.

## First ten fresh-session execution prompts — do not execute now

Each prompt is self-contained in its constraints and exact acceptance target, but requires reading the repository plans. A session receiving this prompt still needs authorization for any filesystem/database/test writes and approved ADRs. No automatic package chaining.

### Prompt P01

> Implement ONLY P01: Preserve audit cases and immutable release evidence, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: none must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY docs/release/; tests/remediation/test_oct15_audit.py (new); apps/web/playwright.full-audit.config.ts; backend/application/production_env_validator_v1.py and directly required new regression tests/docs. Goal: Create a new evidence namespace and append-only manifest; reconstruct 24 named assertions without executing engines in unapproved environments; never edit original reports. Capture source/dependency/config fingerprints and explain artifact mismatch. Acceptance: 24 original cases mapped with provenance and independently expected outcomes; 10 historical failures retained; initial expected failures cannot count as release acceptance; new runs use unique output paths and nonzero failing assertion exit codes. Required tests: Unit: manifest mismatch, duplicate run ID and tampered report rejection; static count/ID reconciliation; later authorized reconstructed suite. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Recording secrets or accidentally relabelling reconstructed evidence as original. Recovery: Revert only new harness/docs in implementation branch; retain all evidence already written. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 3–5 engineer-days; required reviewer QA lead + release engineer.

### Prompt P02

> Implement ONLY P02: Approve model, numerical and surface decisions, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P01 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY backend/services/canonical_project.py; canonical_record.py; canonical_canvas.py; engines/surface_engine.py; apps/web/app/utils/canonicalCanvasProject.ts; docs/remediation/ and directly required new regression tests/docs. Goal: Write approved ADRs for authoritative representations, result failures, unit/datum metadata, node/cell/TIN conventions and migration policy before semantic changes. Inventory roundtrip contracts; do not replace schema v1 blindly. Acceptance: Named architect and PE approve numerical/sampling decisions; owner matrix and legacy ambiguity rules published; no unknown unit/datum becomes assumed feet; migration fixtures selected. Required tests: Contract snapshots for v1/legacy documents and unsupported future versions; no calculation changes in this decision package. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Premature schema lock-in, silently treating old arrays as nodes. Recovery: Docs/contract-only revert; preserve baseline fixtures. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 4–7 engineer-days; required reviewer Principal architect + PE.

### Prompt P03

> Implement ONLY P03: Repair hydrology result contract and invalid-input handling, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P01, P02 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY engines/hydrology_engine.py; backend/planning/runtime.py; planner.py; backend/application/job_workflows.py; backend/planning/hydrology_stage_runners.py and directly required new regression tests/docs. Goal: Use authoritative total_runoff_cfs and explicit missing-result failure, not getattr zero. Recommend typed internal input errors translated to structured boundary failures; preserve valid zeros. Trace C/I and peak consumers, version changed engine results and label unsourced Tc/rainfall assumptions. Acceptance: One-acre C=.625 I=4 gives 2.52 cfs through real helper and affected job/planner paths; invalid/nonfinite/missing inputs never success; explicit empty/zero semantics approved; no invented rainfall/Tc becomes verified. Required tests: New hydrology contract/domain/imperial-metric/adapter/integration tests plus existing real-math and relevant job tests; distinguish no catchment from valid zero. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Changing defaults may expose formerly hidden failures and alter downstream sizing. Recovery: Roll back reader-compatible code only; retain new result versions/history; mark affected old results unverified and do not reactivate unsafe calculations. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 4–8 engineer-days; required reviewer PE + senior backend reviewer.

### Prompt P04

> Implement ONLY P04: Unify detention volume, curves and conservative routing, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P02, P03 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY engines/detention_engine.py; backend/planning/hydrology_stage_runners.py; tests/test_real_math_big_pass.py and directly required new regression tests/docs. Goal: Use one approved integrated stage-volume function for rectangular geometry and curve increments. Define monotone discharge/initial storage/time units; solve routing with explicit residual/error reporting, bounded timestep and supported overtopping behavior. Acceptance: 100x20x5,4:1 volume 24666.666667 ft3; direct and final curve volume agree within registered tolerance; square/unequal basins pass; no clamped water level hides excess storage; mass balance and step-halving convergence pass reviewed thresholds. Required tests: Analytic prism/square/unequal/tapered cases; terminal partial stage; zero outlet/inflow; nonmonotone times/curves; empty/nonfinite inputs; overflow and drawdown; h,h/2,h/4. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Changed storage can change recommended geometry and existing alternatives; routing scope may need restriction. Recovery: Keep old results read-only with method/version tags; disable affected exports during rollback; never rewrite historical numeric values. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 6–12 engineer-days; required reviewer Hydrology PE + numerical reviewer.

### Prompt P05

> Implement ONLY P05: Introduce explicit surface compatibility and registration, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P02 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY engines/surface_engine.py; engines/earthwork_engine.py; backend/planning/civil_surface_model.py; backend/planning/existing_conditions_importers.py and directly required new regression tests/docs. Goal: Define metadata-bearing comparison inputs with CRS, XY/Z units, datum, origin, bounds, spacing, affine orientation and sampling semantics. Reject unknown/mismatched alignment; resampling is a separate explicit, sourced operation with error budget. Acceptance: 1000-ft displaced grids rejected with field-level reasons; equivalent known units can convert explicitly; unknown datum/rotation/NoData cannot be silently aligned; legacy files remain loadable as unverified. Required tests: Translated/rotated grids, differing resolutions, survey feet/international feet, metric, vertical offsets/datums, affine/NoData/bounds mismatch; resampling analytic-plane preservation. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Rejecting formerly accepted comparisons; metadata migration ambiguity. Recovery: Additive adapter rollback keeps original metadata and arrays; never relabel coordinates or reverse conversions implicitly. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 5–10 engineer-days; required reviewer Geospatial engineer + PE.

### Prompt P06

> Implement ONLY P06: Correct grid/TIN earthwork integration and factor order, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P02, P05 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY engines/earthwork_engine.py; engines/grading_engine.py; engines/surface_engine.py; backend/planning/civil_surface_model.py; tests/test_real_math_big_pass.py and directly required new regression tests/docs. Goal: Implement approved cell-domain integration for node surfaces and explicit cell footprints for rasters; clip partial cells and integrate sign-changing cut/fill separately. Use one shared verified integration path; define strip/shrink/swell order and report raw vs adjusted volumes. Acceptance: 3x3 nodes over 20x20ft raised1ft =400ft3; planar slopes, sign changes and clipped domains satisfy analytic conservation and resolution convergence; node/cell/TIN equivalents agree within PE-approved budget. Required tests: Flat/tilted/wedge/two-triangle surfaces; irregular boundary/holes/partial cells; nulls; resolution sequences; m3/ft3/yd3; shrink/swell/strip factors; old fixtures explicitly annotated rather than changed to observed answers. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Material changes to grading, quantities and costs; boundary conventions affect persisted surfaces. Recovery: Preserve source surfaces and prior results; version new engine and recompute explicitly; rollback blocks new-method exports if reader incompatible. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 8–16 engineer-days; required reviewer PE + numerical/geospatial reviewer.

### Prompt P07

> Implement ONLY P07: Constrain GIS and other outbound network requests, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P01 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY backend/planning/gis_provider_registry.py; backend/planning/existing_conditions_online.py; backend/application/file_workflows.py; backend/api/app.py; backend/scripts/imagery_detection_gateway.py and directly required new regression tests/docs. Goal: Centralize outbound policy: approved HTTPS destinations, validated resolved public addresses, revalidated redirects and connected peer, byte/time/concurrency caps; reject credentials/alternate encodings and unsafe schemes. Plan network egress restrictions without buying services. Acceptance: Loopback/private/link-local/metadata/IPv6/rebinding/redirect cases denied before connection; approved current GIS providers still work with mocks; owner-configured private providers require explicit isolated deployment exception. Required tests: Fake resolver/transport tests, redirect chains, slow/oversized/compressed responses, userinfo/IDN/IP encodings and provider regressions. No live exploit. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Breaking legitimate GIS hosts, TOCTOU between DNS validation and connect, proxy route bypass. Recovery: Rollback policy code only with affected endpoint disabled; never reopen arbitrary URL access. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 4–8 engineer-days; required reviewer Application security reviewer + GIS maintainer.

### Prompt P08

> Implement ONLY P08: Stable authentication and distributed abuse controls, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P01 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY backend/api/app.py; start_backend_api.sh; backend/services/auth_store.py; .github/workflows/ and directly required new regression tests/docs. Goal: Use independent trusted-source and normalized-account limits; invalid bearer headers never change login buckets. Choose shared atomic TTL-backed counters or managed edge limits plus application controls; trust forwarding only from explicit proxies. Bound keys, log redacted events, avoid permanent lockouts. Acceptance: Rotating arbitrary bearer/XFF headers cannot evade source/account limits; multiple instances enforce aggregate policy; TTL/cardinality bounded; legitimate shared-IP users and recovery tested; outage behavior documented. Required tests: Mock clock/proxy identities, concurrent workers, malformed auth, IPv6/NAT, account-target distribution, counter outage/fail-closed expensive actions, Retry-After and non-enumerating responses. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Overblocking NAT users; shared-counter dependency failure; account lockout abuse. Recovery: Feature-controlled limiter transition and monitored fallback with equal/better abuse protection; no disable-all rollback. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 6–12 engineer-days; required reviewer Security reviewer + platform engineer.

### Prompt P09

> Implement ONLY P09: Make design writes conflict-safe across every writer, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P01, P02 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY backend/services/project_store.py; backend/services/project_revision.py; backend/application/project_snapshot.py; backend/application/chat_workflows.py; backend/application/job_workflows.py; backend/application/source_context_workflows.py; backend/application/plan_pdf_workflows.py; apps/web/app/hooks/useDashboardProjectSave.ts and directly required new regression tests/docs. Goal: Inventory direct SQL and every read-modify-write. Require CAS for design aggregates, atomic field-owned updates for metadata and independent collaboration rows, locked input/result checks for results. Preserve existing revision-aware wrapper and archive changed-input calculations; do not blanket-retry stale full snapshots. Acceptance: Two edits yield one accepted revision and an explicit recoverable conflict; delayed chat/AI/job cannot overwrite newer geometry; comments/presence do not invalidate unrelated edits; SQLite and PostgreSQL atomicity tested. Required tests: Barrier-controlled UI/job/chat/import races, permission revocation, retry/duplicate commands, interrupted transactions, copy/replace recovery, metadata/result coexistence and branch history. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Deadlocks, conflict storms, broken legacy writers, lost history or tenant authorization. Recovery: Expand/contract writer rollout; preserve recovery snapshots; disable unsafe writers if reverting; no destructive schema rollback. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 8–16 engineer-days; required reviewer Senior backend/data-integrity reviewer.

### Prompt P10

> Implement ONLY P10: Migrate session storage, expiry and revocation safely, after explicit authorization. Repository: /Users/tommychoe/Documents/Playground/Civora AI. Read docs/remediation/CIVORA_MASTER_REMEDIATION_PLAN.md, CIVORA_ISSUE_REGISTER.md, CIVORA_IMPLEMENTATION_BACKLOG.md and applicable domain plan/AGENTS.md. Reinspect current revision against planning baseline ab7db888e85fb9b6125551ecff769d08e0ca7322; preserve dirty user work. Dependencies: P01, P02 must have accepted evidence; numerical/schema policy needs explicit architect/PE approval, not inference. Target ONLY backend/services/auth_store.py; backend/services/database.py; backend/api/app.py; apps/web/app/utils/auth.ts; apps/web/lib/api.ts and directly required new regression tests/docs. Goal: Store keyed/token digests or secure hashes of random tokens with explicit idle/absolute expiry and revocation. Decide bearer-vs-cookie boundary with P13; use additive migration, bounded legacy exchange or deliberate reauthentication; never retain indefinite raw-token fallback. Acceptance: DB read no longer yields usable new sessions; expiry/logout/all-device revocation/rotation enforced; concurrent tabs/devices behave per policy; old records never become permanent bypass; login failure reveals no identity. Required tests: Clock-boundary/rotation-replay/session-fixation/logout races; legacy migration and roll-forward; no token in URLs/logs/files; unauthenticated endpoints unaffected. Use independent expected values; never copy observed output into an oracle, weaken security, remove failures or overwrite old evidence. No unrelated refactor, package installation, production access, network/paid calls, migrations, deployment or commits without separate approval. Run only authorized disposable-local tests, using backlog command templates after inspecting imports/fixtures; no execution against existing data. Risks: Unexpected logout, migration incompatibility, CSRF if cookies introduced. Recovery: Prefer forced reauthentication/roll-forward over restoring raw long-lived credentials; keep additive columns until compatibility proved. Stop if scope/decisions exceed authorization. Return files/why, revisions, exact commands/results/artifact hashes, compatibility proof, reviewer-needed items, unresolved issues and rollback status; do not claim engineering-grade readiness or start another package. Effort budget estimate: 5–10 engineer-days; required reviewer Security reviewer + backend lead.
