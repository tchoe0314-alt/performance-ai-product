# Civora — failure-focused repository audit and complete repair sequence

Date: October 15, 2026. **Audit and plan only. No application repair performed.**

## 1. Executive result and exact boundary

Civora's selected compatibility behavior works, but engineering defects and security/data-integrity gaps remain. Passing a broad existing regression suite does not establish the independent analytical correctness of its expectations.

Inspected checkout: `ef22d42c4647e15cd0d6815b9d3816702cf9dbb4`; branch `codex/remediation-p02-contract-decisions`. Application sources remain those of `ab7db888e85fb9b6125551ecff769d08e0ca7322`; P01 added tests/evidence only. The eight original plans and P02 preparations were already untracked and are preserved unchanged. This audit adds new local evidence/report/script and a fresh P02-run namespace, not application code. No commit, push, production, payment, paid API, migration, package install or real customer record access.

**This is a repository-wide feature/source inventory reconciliation plus fresh failure-focused pure verification, not an exhaustive end-to-end or live website audit.** No complete backend suite, browser suite, DB race, restore/load or real-provider test was executed. Those require a reviewed disposable environment with strictly isolated storage/network and are explicit tasks below. Do not substitute old results or claim every path was exercised.

Fresh checks retain failures, not xfail/skip. Final fresh lanes:

| Lane | Executed | Passed | Failed | Errors/skips | Meaning |
|---|---:|---:|---:|---:|---|
| P01 reconstructed audit | 24 | 14 | 10 | 0/0 | Same original failure conditions still exist |
| P01 evidence harness | 18 | 18 | 0 | 0/0 | Evidence/safety helpers work in selected tests, not product acceptance |
| P02 compatibility | 26 | 26 | 0 | 0/0 | Selected current pure adapters/fixtures preserve tested contracts |
| Expanded independent diagnostic probes | 12 | 2 | 10 | 0/0 | Additional boundaries/alternate paths and version validation fail |
| Selected existing engineering regressions | 16 | 16 | 0 | 0/0 | Existing expectations pass, including some disputed grid conventions |

96 test-method executions in these final lanes: 76 pass/20 fail. **Not 20 independent bugs, not an overall reliability percentage.** The first expanded run had one harness field-name error (E06); its evidence is preserved. Correcting the harness to use the actual `water_surface_elev_ft` field produced a normal product failure in a separate final run. No expected result or application behavior changed.

Static reconciliation rehashed **730 application/tooling source files** against P01 inventory, with no source changes. Existing discovery has 125 route locators,34 supporting/engine modules,662 lexical controls,8 frontend entries and60 curated capability/provider/format records. This audit discovers203 top-level Python test files with2,031 test function/method definitions and143 browser spec files. Counts exclude parameterized expansion/subtests/nested remediation files; different historical discovery scopes need not have identical file totals. Source discovery is not semantic review or runtime verification of all files/features.

## 2. Every original failing assertion and planned repair

All rows below are **freshly reproduced FAIL**, not merely inherited audit statements. Severity is High for the intended engineering/security scope; priority is P0. Root group labels distinguish ten assertions from seven original groups.

| Cases / issue | Observed vs required behavior | Source / cause | Affected or potentially affected paths | Fix and acceptance |
|---|---|---|---|---|
| A03/A04/A05 — ENG-02 | Negative area→successful-6.4512cfs; C1.5→successful12.096; NaN rainfall→successfulNaN; must reject | `engines/hydrology_engine.py:23` unconditionally returns success | Any direct caller; invalid values can reach summaries/serialization if no later guard | P03: engine-level domain/finite/type validation; typed/structured contract decided consistently; test negative/missing/bool/NaN/Inf/zero and caller handling; invalid results never active success |
| A09/A10 — ENG-03 | Unequal basin direct24,164.633843973ft³, curve24,661.586710288; analytical24,666.666666667 | `engines/detention_engine.py:146,176,192`; geometric-mean frustum approximation differs from exact rectangular integral; mixed terminal path | Basin sizing/alternatives, stage/storage reports and routing using the curve | P04: one versioned exact integral for stated geometry and interval differences; independent rectangular/square/partial-depth cases; no simply matching two wrong numbers |
| A11 — ENG-01 | Planner helper0cfs instead of2.52 for the synthetic acre/C=.625/I4 | `backend/planning/runtime.py:947,958` reads `total_flow_cfs`; result owns `total_runoff_cfs` | `planner.py:9989` and drainage-only `job_workflows.py:1670`; C/I can also be consumed separately, so not all pipe sizes proven zero | P03: required result-field access, explicit failure on contract mismatch, preserve valid zero; trace actual downstream peak/C/I consumers through isolated job/planner/export tests |
| A21 — SEC-01 | Fake transport invoked for loopback URL; must block before transport | `gis_provider_registry.py:797` and `/api/gis/provider-health`; caller-controlled service URL | Other GIS/file online-fetch paths need common egress review; no real compromise attempted | P07: destination policy, DNS/IP and redirect validation, scheme/size/time limits, infrastructure egress where available; fake loopback/private/link-local/redirect/rebinding negative tests and approved-provider positive controls |
| A22 — ENG-04 | 3×3 nodes over20×20ft,+1ft→900ft³; expected400 | `earthwork_engine.py:277`; nodes each assigned a whole cell although constructors are node-inclusive | Earthwork/quantities/cost and other implementations below | P02 decisions→P05 registration→P06 shared supported-domain integration; analytical uniform/plane/clipped/cut-fill/NoData/refinement/factor tests; preserve original grid semantics/history |
| A23 — ENG-05 | Same-shaped grids displaced1,000ft accepted as compatible | `earthwork_engine.py:140,156`; shape/spacing only | Direct compatibility validation, legacy wrapper and alternate comparison | P05: compare units/CRS/Zdatum/origin/bounds/affine/sampling; explicit resampling only with new identity/provenance; field-specific reject and aligned positive controls |
| A24 — SEC-02 | Arbitrary bearer strings change throttle identity for same source | `backend/api/app.py:266` hashes unvalidated bearer text | Authentication-abuse bucket before user verification; proxy/replica constraints still untested | P08: independent trusted-source and account-target limits; authenticated identity only after validation; shared state, bounded retention, trusted proxy policy; adversarial headers cannot reset limits |

## 3. Expanded findings and why the old tests missed them

Final probes are E01–E12 in `run_audit.py`; exact tracebacks/observations in `evidence/audit-20261015-02/expanded_probes.json`.

| Probe | Fresh result | Classification / repair mapping |
|---|---|---|
| E01 negative rainfall | success with-1.6128cfs | Additional ENG-02 domain case; not a separate root bug |
| E02 infinite rainfall | success with infinite runoff | Additional ENG-02 finite-value case |
| E03 Boolean area | `True` treated as1 acre, success3.2256cfs | Additional ENG-02 numeric-type case |
| E04 negative C | success with negative runoff | Additional ENG-02 domain case |
| E05 depth5.01 terminal stage | Storage drops from24,661.586710288 at105.0ft to24,246.212315934 at105.01ft | Confirmed inconsistent terminal-curve path under ENG-03/P04; monotonicity and fractional terminal increments must be required |
| E06 zero-outlet100cfs for1hr |360,000ft³ stored beyond curve maximum24,661.586710288 while stage stays105ft; no overflow/unsupported result | Reproduced ENG-03 routing-limit failure mode; add explicit supported-range/overflow contract, conservation and timestep tests, not only storage-formula patch |
| E07 grading volume |900 rather than400ft³ | Same node-area error in `grading_engine.py:689`; P06 must cover grading too |
| E08 surface comparison volume |900 rather than400ft³ | Same node-area error in `surface_engine.py:940`; P06 must cover comparison/UI payload too |
| E09 shifted comparison | Direct `compare_surfaces` compares unrelated domains without error | Alternate unchecked path for ENG-05/P05; centralize registration validation, not just public validator patch |
| E10 Boolean model-adapter version |Backend accepts JSON `true` as adapter version1 | **New confirmed contract-validation defect CAN-01.C1**, Medium/P1; `canonical_record.resolve_model_input` uses loose Python equality. TypeScript source uses strict `model.version !== 1`; canvas Python adapter already rejects booleans. New reviewed child repair under canonical contract work; reject Boolean versions consistently without dropping legacy fields |
| E11 explicit stale revision |Correctly raises conflict | Positive control; do not describe all revision protection as absent |
| E12 Boolean canvas version |Correctly rejects | Positive control showing backend model/workspace validator inconsistency |

The inherited register contains51 parent issue records,11 previously code-confirmed defect/vulnerability records and many uncertainty/evidence items—not51 confirmed bugs. Keep those parents; add CAN-01.C1 as a linked child rather than silently changing historical totals. The alternate paths and detention edge cases extend existing parents; do not count each failing test as a new independent issue.

**Why16 existing tests can pass:** selected `test_real_math_big_pass.py` and three TIN tests include output/existence/internal-formula comparisons and manually constructed2×2 grids whose stated bounds conflict with node semantics. `test_surface_comparison_reports_cut_fill_cells` explicitly expects the current per-node whole-cell totals. Passing that regression does not validate domain integration. Keep the test/history; document the convention decision and replace contradictory expected values only with approved independently derived fixtures, not to force green output.

## 4. Browser-failure reconciliation — no made-up root causes

Historical `/tmp/civora-full-browser-20261014.xml` matches the preserved SHA `be9bf0d3912af0ff7c3e51934807c19de213b3cc3e310d23e1bf6addcd5df99c`:701 cases,23 failures,15 skips,0 error children. This still differs from the pasted700/21fail/1error/16skip account; replacement/timing remains UNKNOWN. Raw logs were not copied to public evidence; the new artifact lists test names and bounded failure classifications only.

**21 failures show expected HTTP200 but received429 at account setup.** They do not independently prove that downstream save/history/group/share functionality failed. They also are not passes; those journeys remain unverified in that run. Preserve rate-limit protection. Plan a dedicated disposable test environment, paced/account-pooled fixture setup or a separately reviewed test-only provisioning seam, and separate abuse-limit tests from ordinary workflow journeys. Do not evade protections with arbitrary bearer strings, spoofed IPs, skip/retry substitution or production limit increases.

| Historical spec / cases | Signal and next verification |
|---|---|
| `phase1-local-tab-branches`3 |Account429; after isolated provisioning, verify first-edit copy/replace/cancel and multi-tab design protection |
| `phase1-local-transactions`5 |Account429; verify persisted undo/redo, failed-save recovery, group/chat atomic undo, branch retention |
| `phase2-project-actions`1 |Account429; viewer default, sharing permissions and named history |
| `phase2-project-header`2 |Account429; identity/autosave persistence and first-edit branch choice |
| `phase2-workspace-environment`1 |Account429; layer/memory must not mutate design/calculation fingerprints |
| `phase2-workspace-layout`1 |Account429; per-user cross-context layout without design revisions |
| `phase2-workspace-stages`1 setup +1 UI |One account429; the844×390 UI failure reports **serious color-contrast** violations. Inspect exact foreground/background in rendered state, fix contrast without weakening Axe, rerun target viewport and responsive/keyboard tests |
| `phase3-local-brief-classification`1 |Account429; verify shared viewer read-only behavior |
| `phase3-local-brief-summary`1 |Account429; verify independent brief state without project writes |
| `pilot-brief-editing`2 |Account429; explicit overrides/original restoration/source supersession and undo |
| `pilot-calculated-workflow`3 |Account429; valid positive calculated save/reopen and honest blocked negative path still need actual execution |
| `phase5-autofix`1 |Login `.ok()` false; HTTP status/root cause unavailable from the retained assertion. Reproduce with sanitized status/timing capture in disposable environment; do not assume429 or a drainage-engine failure |

All spec paths are under `apps/web/tests/live/`.15 skipped cases must be classified by environment/provider/browser/unsupported scope before acceptance. **No browser rerun occurred in this audit**: starting the existing app can initialize real configured stores/providers. P21 and P20 need a reviewed isolated local server/config/storage plan before execution. Existing subscriptions do not by themselves prove test isolation.

## 5. Security, data and feature audit beyond those assertions

These are current-source reconfirmations or explicitly retained risks, not new live exploits. No production keys/data/provider state was inspected.

| Area / status | Evidence and consequence | Concrete repair / acceptance |
|---|---|---|
| Verified enrollment — confirmed code weakness |`auth_store.register_user` issues token without email proof; `project_store.invite_project_member:1167` automatically grants an existing matching email |P10/P11: expiring one-use invitation bound to verified address/account; safe existing-user flow, revocation and role/tenant tests |
| Session lifecycle — confirmed code weakness |`auth_store:114,177` reads/writes raw bearer token, no expiry predicate |P10: token hash storage, expiry/rotation/revoke, migration/reauth policy and multi-device tests; preserve access intentionally, not silently permanent sessions |
| Proxy/distributed throttling — credible runtime risk |Unconditionally trusts first forwarded IP, process-local dictionaries, growing keys (`app.py:266–290`) |P08: trusted proxy topology, shared stable limits with bounded TTL; spoof/replica/lockout/recovery tests |
| Upload overwrite — confirmed destructive code path, not executed |`file_workflows:130–180` reuses user+filename, opens `wb`, cleanup unlinks target on oversize |P14: unique immutable source identity/hash, temp staging and atomic publish, failed upload cannot truncate/delete original; same-name/oversize/interrupt tests in temporary files only |
| Lost writes — credible unverified race |`chat_workflows:5607` saves a loaded full record without expected revision; `check_revision` does nothing when expected omitted |P09: inventory every writer, mandatory design CAS/scoped patches, archive-only changed-input job completion; barrier-driven UI/chat/job/import/export/revoke tests on isolated SQLite/PostgreSQL |
| Existing concurrency protection — present |`project_snapshot` wrapper and explicit revision conflict already exist; E11 passes |Preserve working path; do not wholesale rewrite. Extend coverage to unguarded writers |
| Learning consent — conditional risk |Learning log defaults off, global enable path appends interactions without evident per-user check |P12: consent at collection boundary, org policy/minimization/redaction/retention/delete tests; keep disabled if unqualified |
| Diagnostics/browser hardening — code weakness/risk |Authenticated debug endpoints lack operator restriction; JS-readable session storage and no CSP in inspected Next config |P13: operator role and minimized diagnostics; chosen browser session/CSP strategy tested. No demonstrated XSS, leaked token or current edge-CSP claim |
| Dependencies — UNKNOWN current advisories |Prior scans are historical, not a fresh full Python/JS/dev/container/action audit |P17: inventory/SBOM and fresh advisory scans in approved networked tool environment; review exploitability and dependency changes separately |
| Canonical consistency/growth — PARTIAL / risk |Selected adapters pass26 checks; aggregate/input/result projections and copied checkpoints persist |P02 choices→P09 writers→P15 dependency closure→P16 job/result references and measured growth budgets; do not equate roundtrip tests with a universal parametric kernel |
| GIS/terrain/CRS — PARTIAL |Source attribution/missing-data structures exist, but provider coverage, survey control and datum transforms not qualified |P05/P07/P14/P18/P27: registered rights-cleared inputs, provenance, known transforms, coverage gaps; no surveyed utility depths invented |
| AI/imagery — PARTIAL / NOT TESTED |Commands/fallback/assumptions exist; semantic truth and real imagery/provider cost not demonstrated |P35 fake-provider semantic/evidence/action permission tests; P36 real-provider evaluation only after explicit cost/network authorization; no model learning enabled by audit |
| Exports — PARTIAL |Current drawing-only scope/freshness guards exist; full calculated/external CAD acceptance missing; native DWG/Civil3D unsupported |P20/P34: bound inputs/units/result and target-tool roundtrip with independent expected geometry; distinguish drawing-only vs calculated; disclose unsupported native formats |
| Billing — MISSING operational subscription/enforcement |Stripe status says charging disabled; `usage_gate` returns allowed=True,hook_only |P28–P31 after safety: approved catalog, sandbox lifecycle/webhook/idempotency/reconciliation, seats and server limits; not required for free invitation pilot; no charges in audit |
| Operations/usability/rights — NOT VERIFIED |No current full restore, load, alerts, independent unaided user, current rights/legal/IP acceptance established |P22–P27/P32: exact candidate recovery/capacity/alerts/support/rights/user-task evidence; source code cannot prove external operational/commercial success |

## 6. Ordered implementation plan — incremental, not a rewrite

These are proposed future packages, **not authorized execution in this audit**. Estimates are inherited rough engineer-days, not elapsed days; no promise that all remaining unknowns are included. Existing full package contracts/dependencies/risks/review/rollback are in `../CIVORA_IMPLEMENTATION_BACKLOG.md`; this report sharpens their required regression scope.

| Order | Packages / rough effort | Exactly what changes | Required proof / dependency |
|---|---|---|---|
|0 |Finish decisions/internal review P02; original4–7days total |Accept authority/error/zero/unit/sampling/migration decisions for implementation; select scope; add CAN-01.C1 strict version child |No schema/method change merely from drafting. Preserve v1 fixtures. Qualified method review distinct from signing/sealing |
|1a |P03,4–8days |Hydrology authoritative result field; reject invalid/nonfinite/bool/missing inputs, meaningful zero/no-catchment distinction; safe API/job propagation |A03/04/05/A11 andE01–04 pass under independent expectations; actual job/planner input/result/report traces; valid controls stay unchanged |
|1b |P07,4–8days; P08,6–12days |GIS egress boundary and stable abuse/proxy limits using existing infrastructure |A21/A24 plus redirect/DNS/private/proxy/replica negative and allowed-provider positive tests. These can be separately authorized in parallel with math after shared-file ownership coordination |
|2a |P04,6–12days after P03/decisions |Shared rectangular integral, monotone curves incl fractional terminal interval; explicit routing limits/overflow and continuity/convergence |A09/10,E05/06; direct and curve independently correct, no hidden excess-water stage, mass/time tests; no unsupported solver claim |
|2b |P05,5–10days →P06,8–16days |Registered node/raster/TIN domains; enforce compatibility in **all** entry points; integrate cells/triangles/clipped domains consistently |A22/23,E07–09; test earthwork, grading, compare helper, quantities/cost/export and invalid/null/partial/sloped/cut-fill/factor cases. No blanket multiplier or reinterpretation |
|2c |P09,8–16days; P10,5–10days →P11,6–12days |Conflict-safe every writer, session migration/expiry and verified invitations |Existing revision-aware path preserved; no stale overwrite/cross-tenant access; old project/session migration and failure rollback reviewed |
|3 |P12/P13/P14/P17,4–8 /5–10 /4–8 /4–8days |Consent, operator/browser boundary, immutable uploads, supply-chain qualification |Review relevant failure modes in section5; no enabling optional unsafe features to test them |
|4 |P15/P16,8–16days each |Typed dependency closure, cheap updates vs explicit heavy reruns; separate editable data from checkpoints/results |Move/resize/elevation/source/price/undo changes invalidate exact dependents; archive prior results; repeated cycles show bounded growth and no lost geometry/history |
|5 |P18,75–150days parent qualification; scope into2–8day children |Independent benchmark packs for **every advertised** engine family, not one giant patch |Hydrology, detention, TIN/contours/grading/earthwork, catchments/inlets/storm hydraulics, sanitary/water/fire/vent, utilities/conflicts, roads/cul-de-sac, quantities/cost, layouts/bridge/compliance, AI actions; document unsupported claims; no accuracy claim from old tests alone |
|6 |P20,10–20days; P21,6–12days; P34,8–16days |Complete positive/negative engineering journey and repeatable supported-browser/accessibility/CAD acceptance |Safe provisioning resolves test setup without weakening auth; rerun **full** suites, preserve first failures; fix contrast; externally verify advertised units/content; no native CAD fiction |
|7 |P22,8–16days; P23,8–16days; P25,4–8days |DB+artifact+job restore/rollback, measured project/concurrency envelope, alerts/incident/support |Explicit isolated restore/load plan, approved resource budget, measured limits and failure recovery; current hosted checks/deploy need separate approval |
|8 |P19/P26/P27/P24,6–12 /6–12 /8–16 /4–8days |Scope-specific independent method/export/user review, rights/IP/legal controls and exact hosted candidate qualification |User engineers retain their own professional responsibility; Civora never stamps; independently reviewed methods and trustworthy output still required. No blanket claim every discipline/place is ready |
|9 |P28–P31,29–58days combined |Approved paid catalog, payment lifecycle, entitlements, seats/support/data lifecycle |After safety/operational scope acceptance; sandbox before any approved real transaction; separate payment/spend authority |
|10 |P32/P33/P35/P36 per existing dependencies |Diligence/value evidence, targeted maintainability, AI semantic/provider qualification |P35 before beta if AI actions enabled; don't postpone AI safety to billing. P36 real-provider cost permission; P33 not a rewrite. Investor claims require actual customer evidence |

Dependencies in the original backlog take precedence over this compressed presentation. P27 rights/reviewer preparation can start alongside repairs; P17 inventories can start early. P19 needs qualified benchmark/connected/export evidence. P21 triage/isolation design can start now, but final browser acceptance follows repaired integration. One owner at a time for shared `app.py`, `project_store`, `job_workflows`, canonical adapters, `surface_engine` and `planner`; no automatic agent delegation or parallel conflicting edits.

Original full36-package program estimate294–586engineer-days plus discovery reserve370–820; **not a new quote for the seven original bugs**, and includes wide qualification/commercial/operations scope. New/uncertain defects may change it. Reduce the first release to a justified supported subset rather than claiming all disciplines work. A focused original-math repair lane P03/P04/P05/P06 is23–46engineer-days before external review/integration; security and data integrity are additional, not optional launch costs. Avoid new planning loops: after decisions and named package authorization, repair a bounded package, retest affected paths, then integrate.

## 7. Common implementation and acceptance contract

For each separately authorized package:

1. Record current revision/dirty state and preserve all pre-existing work; branch/package allowlist.
2. Capture the original failure in a normal regression with an independently specified oracle. Preserve historical output; no xfail acceptance or adjusting expected values to wrong behavior.
3. Change the smallest shared source of the defect, tracing alternate implementations/callers. Version numerical semantics and keep prior results inspectable; no silent bulk recalculation.
4. Test valid, invalid, boundary, unit/registration and affected save/history/export paths; API/DB/browser tests only in a reviewed isolated environment. No charges/provider calls/deploy without separate permission.
5. If a new failure is found, classify product/test/environment/unsupported scope; file a linked child ticket and stop relevant acceptance, not hide it.
6. Review application/test diff, source/fixture/dependency/config identity, outcome/skips and migration/rollback. Correct numerical rollback must not re-enable known wrong outputs.
7. Mark a finding closed only when its specific acceptance evidence passes on the candidate; retain missing professional/reference/operational evidence as such. Software-tested is not professionally certified.
8. At phase integration, run clean full backend/browser/E2E/engineering and allowed security suites against a frozen candidate. A targeted retry does not erase a failed complete run. Release gates follow scope evidence, not package count.

## 8. What still must be audited dynamically

Mandatory next audit execution slice: reviewed disposable backend+frontend+test account provisioning, temporary SQLite/Postgres and uploads/artifacts under unique temporary roots, network denied except local test services, explicit fake AI/GIS/image/payment modes with effects distinguished, no real credentials or copied customer data, canary disabled, no automated deploy/learning. Inspect startup/fixtures before running. Record process endpoints, storage paths and effective **redacted** test configuration; enforce them before importing app modules. Preserve rate-limit tests in their own controlled lane.

Then execute: full backend; full supported-browser suite twice for repeatability; positive calculated journey; perturb geometry/elevation/source/price and verify stale/result/save/reopen/export; barrier-controlled races and role revocation; malicious upload/egress/auth cases; independent engineering benchmarks; CAD imports; controlled backup/restore and load. Current audit **does not claim these are complete**.

The existing live website is outside this audit. A true current hosted audit needs an explicitly authorized synthetic test account/project and verified deployment/backend identity; destructive/account deletion/payment tests require stricter isolated treatment. Do not use existing customer data or enable every feature on production.

## 9. Evidence register and custody

- Original audit and51-parent issue register: user-supplied audit, `../CIVORA_ISSUE_REGISTER.md`; preserved unchanged.
- Original P01 24-case mapping/results and manifests: `../../release/p01/evidence/p01-20261015-03/` (historical comparison).
- Fresh24+18+26 run: `../p02/evidence/audit-refresh-20261015-01/`; manifest `4b803e62951dc2418e58dfaeee07c16274fb0805550efe9dc503c25e56a81204`.
- Expanded final probes,16 selected tests, discovery and historical browser names: `evidence/audit-20261015-02/`; manifest `40cd5aac536479b2e6c4f590744302cd454ccd0a3eb491ac9411deb530fa25b6`.
- Initial expanded run, preserved including one harness error: `evidence/audit-20261015-01/`; manifest `4b3978475e203b65a3503898e8a119d60d670146accf250030909b87e99bfe90`.
- Script `run_audit.py` has selected original test bodies/AST loading and explicit fake/in-memory boundaries. No source expectation is edited.
- Local create-only manifests and anchored hashes are tamper-evident under local trust assumptions, not independently protected WORM storage. No external review or custody is fabricated.

Final assessment: **not ready to trust for real engineering outputs or public paid launch**. Selected save/compatibility features pass; that cannot override wrong outputs or incomplete browser/security/operational evidence. The fix plan is incremental and concrete; no full rewrite is justified by this evidence. Next authorized implementation should address the hydrology contract/validation and independently scoped egress/abuse lanes, then registered surfaces/shared integration and detention. This audit itself implements none of those repairs.
