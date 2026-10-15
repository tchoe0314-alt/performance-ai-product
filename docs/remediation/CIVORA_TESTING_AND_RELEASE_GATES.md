# CIVORA TESTING AND RELEASE GATES

Baseline 2026-10-15 / ab7db888e85fb9b6125551ecff769d08e0ca7322. **Planning only: no tests/builds/caches/databases/browser sessions/network calls executed by this task.**
Linked tasks P01/P18/P20–P26/P28–P31/P34–P36; detailed contracts in backlog. Historical results remain historical.

## 1. Reconstruct all original 24 assertions (TEST-01)

Sources: user-supplied full audit and prior tool transcript. No immutable complete original harness file located; original stdout/commands in conversation are the available execution record. Reconstructed tests must carry `reconstructed_from_transcript`, not “original signed harness.” Preserve observed values even after fixes. P01 future tests can intentionally reproduce failures on baseline, but baseline xfail never satisfies release gates.

| Case | Original input / assertion | Historical observed result | Independent expected / required future result | Root issue / repair / downstream |
|---|---|---|---|---|
| A01 | Rational 2ac,C=.8,I=4 | PASS6.4512cfs | 1.008*2*.8*4=6.4512 | Preserve ENG-02/P03; runoff/quantity reports |
| A02 | Empty catchment list, total zero | PASS0 | Original arithmetic total0; future separate no-catchments status per approved contract, never silently verified site hydrology | ENG-02/P03; input completeness |
| A03 | Area -2ac,C=.8,I=4 must reject | FAIL success=True,Q=-6.4512 | Typed/structured invalid area, no successful engineering result | ENG-02/P03; negative sizing/report data |
| A04 | Area2ac,C=1.5,I=4 must reject | FAIL success=True,Q=12.096 | Reject nominal Rational C>1 | ENG-02/P03; runoff/design basis |
| A05 | Area2ac,C=.8,I=NaN must reject | FAIL success=True,Q=NaN | Reject nonfinite at engine boundary and serialization | ENG-02/P03; DB/report/export corruption |
| A06 | Storage inflow10,release2cfs,.5hr | PASS14400ft3 | (10-2)*.5*3600=14400 | Preserve ENG-03/P04; deterministic constant-flow approximation only |
| A07 | Drawdown14400ft3 at2cfs | PASS2hr | 14400/2/3600=2 | Preserve ENG-03/P04; outlet assumptions separately reviewed |
| A08 | Basin100x100ft,depth5,slope4 | PASS72666.666666667ft3 | Analytic integral same value | ENG-03/P04; square case insufficient alone |
| A09 | Basin100x20ft,depth5,slope4 | FAIL24164.633843973ft3 | 24666.666666667ft3 | ENG-03/P04; basin sizing/earthwork/quantities |
| A10 | Same rectangular basin direct vs stage-curve terminal storage | FAIL direct24164.633843973 vs curve24661.586710288 | Both converge to analytic24666.666666667 within approved bound; not simply matching wrong direct value | ENG-03/P04; routing/curve reports |
| A11 | Helper lot w=h208.710325571113ft, impervious21780sf, default intensity4 | FAIL peak0cfs | One-acre C=.625 yields approximately2.52cfs. Existing assumptions remain estimated | ENG-01/P03; runtime helper/job/planner consumers |
| A12 | Repeat same valid Rational inputs | PASS deterministic6.4512 | Same finite result with same inputs/environment | Preserve ENG-01/02/P03; reproducibility |
| A13 | new_project_document(name=synthetic audit), dumps/JSON loads | PASS exact structural roundtrip | No value loss, no guessed CRS/datum | CAN-01/P02/P20 |
| A14 | Canonical document extra top-level section | PASS rejection | Typed schema error; preserve allowed extensions separately | CAN-01/P02 |
| A15 | Canonical project x=NaN | PASS rejection | Finite JSON only | CAN-01/P02 |
| A16 | Canonical document missing units section | PASS rejection | Missing required section rejected | CAN-01/P02 |
| A17 | Road a follows road b, valid road_culdesac link; both carry cul_de_sac_v1 metadata | PASS accepted | Valid typed link accepted | CAN-02/P15 |
| A18 | Dependency a→missing b | PASS rejection | Missing target rejected | CAN-02/P15 |
| A19 | Valid typed road edges a→b and b→a | PASS rejection | Cycle rejected | CAN-02/P15 |
| A20 | Roads a,b both drive c | PASS rejection | Multiple geometry drivers rejected unless future explicit supported solver | CAN-02/P15 |
| A21 | check_provider_health provider URL http://127.0.0.1:9876/private/FeatureServer with FakeSession | FAIL mock get invoked once, status healthy; actual network calls0 | Denied before transport, zero get attempts; approved provider positive controls retained | SEC-01/P07; all outbound paths |
| A22 | GridSurface bounds0..20ft,spacing10,3x3 nodes existing100/proposed101; accepted surfaces, IDs EG/FG | FAIL success=True,fill900ft3 | Supported domain area400sf*1ft=400ft3 | ENG-04/P06; grading/quantity/cost |
| A23 | Same shape/spacing, proposed bounds1000..1020 vs existing0..20 | FAIL validator_success=True | Incompatible origin/bounds failure with field reasons | ENG-05/P05; surface/earthwork |
| A24 | Same source198.51.100.9, bearer unvalidated-token-A vs unvalidated-token-B | FAIL different throttle buckets | Unauthenticated source/account limits independent of arbitrary bearer text | SEC-02/P08; authentication abuse |

Historical total14PASS/10FAIL. Failing A03/04/05 share validation root; A09/10 share storage-formula/curve root; A11 accessor root; A22 grid-domain root; A23 registration root; A21 egress root; A24 throttle identity root. Seven root groups, not ten independent bugs. Expand each with property/invalid/unit/integration cases; do not only hardcode audited values.

Original source helpers were AST-extracted to avoid app initialization for A11/A24, and fake transport used for A21. Those narrow checks are not whole-app integration. New regressions must include actual approved isolated application paths.

## 2. Evidence and test architecture

- Unit/domain layer: pure math + independent oracle, finite/type/domain/tolerance cases, deterministic/property/metamorphic checks.
- Contract layer: legacy/canonical/object/source/result/engine schema boundaries, unrecognized fields/versions, source/status preservation and error translation.
- Integration layer: SQLite and PostgreSQL transactional writers, auth/tenant/roles/jobs/files and revisions in explicitly disposable storage.
- Browser layer: real isolated frontend/backend flows with named mock boundaries; do not return bare success mocks where saved checkpoints required.
- Golden layer: Q01–Q30 independently reviewed reference cases; P18 domain matrix.
- Adversarial layer: egress/auth/session/privacy/upload/AI-injection/concurrency negative cases.
- External layer: PE, actual CAD viewer/import/plot and authorized provider evidence.
- Recovery/load layer: explicit approved isolated environments, never customer production load/restore.
- Commercial layer: sandbox provider and deterministic entitlement ledger; live payment forbidden absent separate authority.

Every fixture records synthetic vs rights-cleared real, original files/hash, units/CRS/datum/source acceptance, expected author/reference/tolerance and enabled scope. “Real input” fixture names in repository are not evidence of survey truth. No measurement means UNKNOWN, not0.

New test path suggestions in backlog are future files, not commands that currently exist. No blanket test execution permitted in planning: imports can instantiate Database and create directories; even auth GET can update last_used_at. Do not assume collect-only is nonmutating. Future execution must inspect imports/fixtures and explicitly set isolated storage with no inherited provider secrets, deny network by default, and authorize cache/report/temp writes.

## 3. Engineering golden program (TEST-02)

Use engineering plan Q matrix. Independent author prepares expected values before observed output. Analytical planes/basin integrals/flow sums supplement official reference methods and licensed reference-tool comparisons. Same-function inverse/roundtrip checks retained as regressions but not independent accuracy evidence. Include valid, boundary, invalid, precision, units, datum, conservation and connected perturbation cases.

Require hash-bound input+expected artifacts, reference edition/jurisdiction/method, reviewer competence/identity, tolerances fixed before comparison and disposition. Distinct scopes: internal computed, estimated, imported/unverified, user assumed, independently benchmarked and professionally reviewed. No single “engineering verified” Boolean can collapse them.

## 4. Positive/negative engineering E2E (TEST-03)

Use small commercial pad and constrained infill fixtures initially; add surface/utility-heavy fixture for scope. At least one rights-cleared real project independently reviewed before Gate B; synthetic success alone insufficient.

1. Verified account and organization/project creation; correct roles/enrollment.
2. Address/context lookup explicitly mock vs authorized provider; absent/ambiguous result visible.
3. Import original survey/GIS files; verify hashes, units, CRS/datum/registration and candidate acceptance.
4. Draw/name/classify/group geometry, establish required engineering basis and protect references.
5. Execute only scope-qualified calculations; inspect each required stage (not just top-level success).
6. Review source/assumption/warning states; failed/missing/stale stage blocks calculated output.
7. Save/reload and cross-tab action preserves geometry IDs and edit/calculation/source history.
8. Move building/road/utility and modify elevation; expected closure stale, approval for heavy rerun.
9. Rerun affected computations; independently compare values and partial/full equivalence.
10. Quantity, price basis and calculation reports reconcile current inputs. Fixture prices labelled synthetic; priced outputs need approved price data.
11. Export saved current drawing vs calculated package with explicit scope; no archived values smuggled in.
12. Independent target CAD import/plot and PE review bound to exact candidate/input/artifact.

Negatives: invalid/noData/datum conflicts, missing utilities/outfall, unknown standard, source revoke, AI-fabricated elevation, corrupt uploads, excessive project, network outage, unauthorized role, cross-tenant ID, delayed job, double Apply, cancel/retry, transaction failure, stale export during edit and unsupported format. Expected outcome includes preserved work and actionable error, not only an HTTP status.

## 5. Browsers/accessibility and failure triage (TEST-04)

Candidate beta policy proposed: latest qualified desktop Chromium and WebKit plus emulated mobile Chromium/WebKit for declared workflows; Firefox NOT supported until independently passing, or explicitly excluded with product approval. Record exact browser/OS/emulation version; no physical-device certification inferred from emulation. Public policy depends on engineer customer needs.

Triage categories: product defect (repair), test defect (justify oracle/helper change), environment (fix/record environment), flake (repeat controlled diagnosis), unsupported (product decision and visible limitations). Each historical fail/skip retains ID, original report/hash, cause/evidence, fix commit or accepted exclusion, new result. A rerun PASS does not erase old failure. Do not skip a supported required test, relax geometry assertions, disable rate limiting or rely on retries to certify stability.

Proposed gate thresholds: two consecutive complete frozen-candidate supported-matrix runs, zero unresolved required failures/flake-only passes; skips/exclusions individually justified and not required scope. Primary workflows have no serious/critical automated accessibility findings; keyboard/focus/zoom/error/screen-reader tasks manually reviewed. Mobile control placement, canvas coordinates, source warnings and export scope tested at narrow/wide aspect ratios. Measure large-project responsiveness separately.

## 6. Recovery/rollout verification (TEST-05)

Authorized isolated drill only: restore DB + upload/source/artifact storage to new environment, no source overwrite. Check original bytes/hashes, object/source/result/history/review/permission references, account state and token revocation policy; restore jobs without duplicate side effects. Corrupted/missing objects must raise explicit recovery exceptions. Verify backup transport/storage encryption through provider/config evidence (not assumed from environment variable), retention, owner and access audit.

Candidate targets for approval: RPO<=24h and RTO<=4h for free pilot; tighten only with evidence. Snapshot timestamps and actual measurements required; historical under5min drill not an SLA. Verify complete customer export/deletion against approved retention/legal holds and backups. Rehearse failed/cancelled jobs, interrupted migration, concurrent startup DDL and old/new writer compatibility. Code rollback must not read/write new semantics incorrectly; otherwise controlled roll-forward or approved restore. No destructive production test.

## 7. Performance/workload/cost matrix (TEST-06)

All numeric budgets are proposed product targets to approve BEFORE optimization/observations; not existing verified capacity.

| Fixture | Objects / vertices | Terrain and utilities | History / users | Intended interpretation |
|---|---|---|---|---|
| S |100 objects/1000 vertices |101x101 terrain nodes;25 utility links |50 edits/10 results;1 user | Narrow ordinary pilot case |
| M |500 objects/3000 vertices |251x251 nodes;100 links |100 edits/25 results;5 simultaneous users | Current drawing-export boundary; calculate limits separately qualified |
| L |2000 objects/20000 vertices |501x501 nodes;500 links |1000 archived edits/100 results;20 users | Stress/out-of-scope case unless qualified; existing export must reject >500/3000 safely |

Measure same release/config/machine/container allocation/data hashes, warm/cold p50/p95/p99, timeout/error counts and individual stages. Proposed S/M p95: interactive visual response<=100ms excluding explicit heavy jobs; save/load<=2s; preview<=2s; supported export<=30s; ordinary scoped calculation<=60s or explicit progress/cancellable job with published higher bound. Fail gracefully outside support. Existing long test timings do not establish these targets.

Concurrency staircase1→2→5→10→20, then stop at declared limits; isolate auth-abuse load from successful engineer workflow load. Bounded queue/backpressure, cancellation/timeout, no pool starvation/unbounded counters. Pilot repeat-cycle/soak target>=4h; public target>=24h within approved resource budget. No external calls in synthetic soak. Track RSS<=60% declared per-worker allocation, CPU/DB connections/locks and total bytes per run; model growth budgets in canonical plan.

Real AI/provider cost requires explicit spend cap and consent/rights first; record tokens/model/retries/cache/time/rate and provider bill reconciliation. Infrastructure cost from actual existing plan invoices/config (authorized/redacted), not guessed. Report cost per successful workflow and active customer with utilization assumptions; unknowns remain unknown. No purchase or production capacity test authorized now.

## 8. Immutable release manifest (TEST-07/08)

Proposed fields: rc_id, full git SHA/clean flag/source tree hash, submodule/model hashes, dependency lock/SBOM/image digests, Python/Node/browser/native-library versions, DB/schema/canonical/engine/method versions, redacted configuration fingerprint and feature/enrollment/source policies, fixture/reference/input hashes, tests/tool/advisory timestamps, outcome counts/skips/exceptions, oracle/reviewer approvals, export compatibility versions, environment identity, deployment frontend/API/worker IDs and hashes, backup/rollback identity, signer/owner/time.

No secret values, raw customer data or tokens in public manifest. Unique evidence location per candidate/run/tool; hash and append-only index, ideally storage write protection. Do not overwrite /tmp paths or rewrite an old XML. Re-running creates new artifact linked by supersedes/reason. Any source/dependency/method/config change invalidates affected acceptance; even docs-only changes recorded, with documented impact assessment rather than silently old SHA substitution. Frozen full-run acceptance occurs AFTER all code changes.

## 9. Objective release gates

Gate owners must be appointed humans before execution. Current disposition for every gate: **NOT TESTED / NOT PASSED**. No program document itself satisfies a gate.

| Gate | Objective pass criteria | Evidence owner / required reviewers | Escalation and exclusions |
|---|---|---|---|
| A Internal correctness | All ENG-01–05 regressions and enabled Q claims pass independent expected values within preapproved tolerance; all invalid/boundary/unit/datum/conservation required cases pass; no unresolved High/Critical wrong supported result; method/version/limitations documented | Engineering lead + QA custodian; numerical/geospatial reviewer and competent PE approves engineering methods/tolerances | Numerical discrepancy blocks affected scope and downstream gates; no cosmetic/old-test waiver; unsupported claims explicitly disabled |
| B Controlled private beta | A for exact beta scope; SEC-01/02/03/04 and applicable High risks closed or independently verified equivalent containment; scoped negative tenant/privacy/upload/concurrency tests pass; verified enrollment; two positive E2Es including rights-cleared real reviewed input; independent PE acceptance; advertised exports accepted; supported browsers pass; current hosted identities and DB/files/jobs restore meet approved RPO/RTO; named support/incident owner and limitations | Release owner + QA; independent PE(s), AppSec, platform/recovery and product/counsel scope review | Missing real/PE/provider access -> NOT TESTED, no beta approval. Optional AI/learning/native formats may be enforceably excluded; not just hidden UI |
| C Public launch | B plus independent beta usability thresholds, two full supported-browser runs; independent security review no unresolved exploitable High/Critical; representative24h soak/recovery/alerts meet declared operating limits; all advertised export/engine/source rights/legal docs reviewed; monitored customer support process exercised | Release/operations + product owner; independent security, QA/accessibility, PE, CAD reviewer and counsel | Material error/exposure pauses enrollment/affected feature; unresolved moderate exceptions need named owner, compensation, expiry and approval; no exception for required wrong outputs |
| D Paid subscriptions | C safe production scope; sandbox catalog/checkout/customer/webhook/lifecycle/refund/trial/tax policy and reconciliation accepted; atomic entitlements/quotas/seats prevent races; support/onboarding/data lifecycle accepted; approved legal docs; no raw cards in Civora | Payments/product owner + QA; independent payment/security reviewer, finance/counsel, customer-test users | No live charges without separate approval. Any duplicate charge/access loss/ledger divergence blocks; free pilot remains free |
| E Investor diligence | Reproducible scoped demo/capability matrix; exact revision-linked engineering/PE/security/test/export/recovery records, closure register and residual risks; architecture/IP/data-rights/cost dossier; external customer evidence included if available with missing traction explicit | Founder/evidence custodian; independent technical reviewer, PE/AppSec/counsel/finance for their sections | May prepare while beta work proceeds; no requirement to invent customers or complete paid launch. Cannot claim PMF, valuation or commercial launch from code |

## 10. Usability study and support acceptance

P26: proposed>=5 independent civil engineers from>=2 firms/teams; separate implementation team, qualifications/tasks/date/source rights recorded. Founder recruitment/contact only when authorized. Controlled task sessions can occur as supervised evaluation before public beta; do not call them independent production use.

Tasks: verify account/invite, create/address project, review missing GIS source, choose units/CRS/datum, draw/name/group/edit, run scoped calculation, interpret invalid/stale result, undo/recover, save/reopen, export correct scope, share viewer vs editor. Score independent vs assisted steps, completion time, critical reliance/data errors, requested help, export failures, units/source interpretation, calibrated confidence and repeat-session use. No coaching during scored attempt; record sample limitations.

Proposed public threshold: >=90% primary task completion, >=80% without critical assistance; zero critical unsafe-reliance/data errors; 100% distinguish unverified/geometry-only vs calculated output; no unresolved severe accessibility issue. Time-to-task compared against predetermined baseline, not invented claimed time savings. Gate B needs supervised safe interpretation/recovery and PE acceptance; Gate C needs independent beta usability/repeat evidence. Satisfaction alone cannot establish correctness.

Support: named monitored owner/contact, synthetic ticket delivered/acknowledged/escalated within approved service target, operator access audited and incident drill performed. Data export/deletion/retention explained before use; actual legal/service terms approved by humans.

## 11. Payment acceptance without card data

P28–P31 after safety foundations: proposed Pro79/Engineer199/Teams149seat/custom Enterprise are draft offers, not current purchasable plans. Product approves feature mapping, monthly/yearly/currency/tax, minimum seats, trials, grace, cancellation date, proration/refund and export rights. Provider-hosted checkout stores no raw PAN/CVV. Stable customer/org identity, verified webhook signature/raw body/time window, unique event IDs and reconciliation ledger required. Out-of-order/duplicate webhook safely converges; server checks rights on action/queue execution/publication.

Sandbox matrix: new/renew/trial-end, success/failure/retry/grace, cancel/resume, upgrade/downgrade/proration, seat concurrency, refund/partial dispute/tax invoice, lost/replayed/forged event, provider outage and repair reconciliation. Paid action reservation/finalization prevents double usage and retry charges. Finance/counsel approve taxes/refunds, not Codex. Test synthetic customer end-to-end subscription/onboarding/support/export/delete; payment and legal-retention records retained appropriately. No real charge or vendor provisioning in this task.

## 12. Result reporting and non-green policy

Report discovered/executed/pass/fail/error/skip/blocked counts separately; coverage line/branch only if measured with source manifest. Mixed mocks/live/demo observations labelled. All current release-required checks need fresh candidate execution; previous PASS is context only. A retry or targeted rerun can diagnose but cannot turn an original complete-run artifact green. Required failures are fixed and full acceptance repeated; any supported test removal needs documented replacement with equal/stronger coverage and independent approval.

## 13. All-feature characterization and interaction coverage

Added founder direction: enumerate and audit every identifiable feature, including currently disabled/optional capabilities, alongside the existing package sequence. P01 owns inventory/coverage IDs; P20 owns integrated acceptance; P18/P35/P36 own domain/provider qualification. Existing and new regressions are never removed for a green dashboard.

Per-feature coverage record: feature_id; UI/control/route/engine/flag and source locator; implementation completeness; enablement prerequisites; user/tenant/role; unit/datum/source state; allowed local enablement; possible writes/network/cost/privacy effects; independent expected behavior; smoke/negative/interaction tests; real vs mock execution; candidate/environment identity; observed PASS/PARTIAL/FAIL/NOT TESTED/UNKNOWN; linked issue/repair/retest. Require every inventory feature to have a disposition; count unimplemented/blocked entries explicitly, never as passed.

Safe modes:
- Pure math/geometry: isolated inputs and independent oracles.
- Stateful project/UI/team/jobs: disposable per-run database/files/test identities, no existing customer data.
- AI/GIS/image/payment adapters: local doubles for deterministic failure/success contracts; real provider evaluation separately authorized and separately reported.
- Billing: sandbox-only when implementation exists; missing checkout remains missing. No real charge.
- Learning: synthetic consent fixtures and disabled default; no real prompt collection/training activation.
- Export/import: generated rights-cleared fixtures; target-tool acceptance external and explicit.
- Deployment/backup: isolated configuration/restore rehearsal; current production gate remains NOT TESTED until authorized.

Sequence: baseline breadth inventory → characterized smoke/negative tests → independently expected defect records → safety-critical repairs in dependency order → targeted affected-feature regressions → full supported-feature/interaction sweep at phase gate and frozen final candidate. Test each incompatible alternative mode separately; use pairwise interaction coverage plus risk-selected triples, not an impossible all-flag Cartesian promise. Include saved-project compatibility after toggles, rollback, undo and background completion. Any mode that cannot safely run remains blocked/unverified with exact missing prerequisite.

“Every feature audited” means every item has an honest evidence-backed disposition, not every feature implemented, enabled in production, or professionally approved. Full production claims remain limited to qualified scope under Gates A–D.

