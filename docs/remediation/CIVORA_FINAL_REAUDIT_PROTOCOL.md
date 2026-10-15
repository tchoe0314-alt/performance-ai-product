# CIVORA FINAL RE-AUDIT PROTOCOL

Planning baseline: October15,2026 / ab7db888e85fb9b6125551ecff769d08e0ca7322.
**Protocol only, NOT RUN. Implementation, external access, tests that write and deployment need explicit authorization.**

## 1. Purpose and independence

Reproduce and extend the original functional-alpha assessment on a precisely frozen candidate. Audit implementation and evidence independently; do not trust package completion statements or prior green runs. Include architecture, feature functionality, engineering, canonical integrity, reliability, security, usability, commercial systems and technical diligence. Preserve all earlier reports. Auditor should not be sole author/approver of fixes; professional/legal/security signoff requires competent humans.

Required inputs: named scope/claims/exclusions, approved ADRs, 51-issue register plus new findings, P-package/child records/fix commits, exact candidate source and dependency images, source rights and independent benchmark/PE records, support/operations/legal decisions and approved test environments/budgets. Missing inputs remain NOT TESTED/UNKNOWN. P03–P06 engineering semantics cannot be accepted just because expected tests were edited.

## 2. Freeze and establish evidence custody

1. Confirm written authorization for each class: local temp/DB/browser writes, provider network, human participation, payment sandbox, staging/deployment, load/recovery and independent security testing. Do not infer production access from code permission.
2. Record full SHA, clean state, source hash, dependency/SBOM/image/native runtime/browser/model hashes, schema/canonical/engine versions and redacted effective config. Stop on changing HEAD or untracked application files. Read applicable AGENTS instructions.
3. Compare to audited baseline and each fix commit; enumerate which changes touch math, compatibility, authorization, exports and tests. Identify any changes after package tests.
4. Allocate new evidence directory/run ID with append-only manifest; hash original artifacts before copying with permission; never reuse audit XML filenames.
5. Preserve original October15 text/transcript as supplied evidence with accurate provenance if not already immutable; do not fabricate a signed old audit. TEST-08 current hash/count mismatch remains recorded until explained.
6. Validate environment is isolated and not using customer data or inherited provider keys. Test APIs/login may write even for apparent GET; deny unapproved network and use synthetic identities/files.
7. Only execute reviewed commands from explicit run plan. No blind pytest collection/npm prebuild that can initialize storage or clean files. Save exact sanitized commands/tool versions and outcomes. Tests produce artifacts only in authorized locations.

## 3. Architecture and feature reinspection

Repeat source inventory and actual wiring: UI controls→API→ownership→job/engine→canonical result→persistence→export. Recheck project/template/units/save/load/version/duplicate/undo/recovery; GIS/geocode/parcels/terrain/utilities/roads/source confidence/transform; drawing/classification/groups/layers/snapping/3D/engineering; AI command/context/memory/assumptions/providers; deliverables/compatibility; users/org/roles/billing/entitlements/support. Classify Fully implemented and verified, Implemented not verified, Partial, UI/mock, Stub, Missing, Unable to determine with file/function/line and current runtime proof. A new button/schema/endpoint is insufficient.

Draw current Mermaid architecture and model ownership diagram. Compare to CAN plan; locate duplicate authoritative writes, omitted sources and compatibility losses. Reassess canonical maturity using actual change propagation, not original3/5 assumption. Stage/maturity and commercial traction reassessed separately; do not automatically promote on ticket closure.

## 4. Engineering verification

- Run reconstructed A01–A24 suite on candidate; explicitly assert all10 original failures now satisfy independent expected behavior while14 original successes preserved or semantically changed with approval.
- Verify each enabled Q-family independent oracle/method/edition/jurisdiction/units/datum/tolerance existed before candidate observations.
- Run invalid/missing/nonfinite/boundary/property/metamorphic cases, conservation and convergence.
- Confirm 2.52cfs helper reaches actual relevant paths; map consumers and do not overgeneralize risk.
- Confirm rectangular basin24666.666667ft3, terminal stage parity and routing residual/overflow/timestep acceptance.
- Confirm400ft3 grid-domain case, planes/sign-changing cut/fill/clipped boundaries, material factor order and1000ft registration rejection.
- Validate surface precision/control, CRS/vertical datum and unsupported resampling; original data retained.
- Run road/building/elevation/utility perturbations through affected closure, stale→review→rerun, undo/reopen, quantities/cost and export. Preserve prior reviewed records by revision.
- Independently replay reference-tool cases and inspect numerical/report unit labels; no same-helper expected values accepted as independent proof.
- P19 independent PE evaluates exact inputs/outputs/artifacts for supported scope, identifies assumptions and limitations; professional approval cannot be generated by an automated test.
- Inspect actual missing/fabricated source/dimension/elevation paths in AI. Enforce source/estimate/unverified distinctions through reports and exports.

## 5. Security verification

Use isolated mock transports and approved test targets, never unauthorized live exploitation:
- SEC01: destination allowlist/DNS/connect/redirect/proxy/IP/response/timeout negatives and approved GIS regressions.
- SEC02/06: arbitrary bearer/XFF/account/source identity, multi-instance atomic counters/TTL/cardinality/outage and fair shared-IP behavior.
- SEC03: preregister victim/unverified identity, invites/ownership/expiration/replay/revocation/org access; closed enrollment positive approved-user login.
- SEC04/09: hash/expiry/rotation/revocation/legacy cutoff/browser session/XSS/CSRF/secure headers/third-party and file-rendering controls; no raw token in logs/reports.
- SEC05: effective personal/org consent, default off, withdrawal race, minimization, retention/export/delete and downstream training lineage.
- SEC07: operator-only diagnostics and support privilege; normal roles denied and redacted synthetic sentinels.
- SEC08: same filename and failed upload preserves old bytes; immutable source/hash, ownership, parser resource and symlink/path bounds.
- SEC10/CAN03: all writer/direct SQL inventory, delayed UI/chat/AI/job/import/export races, retries and interruptions on both DB backends; no stale design overwrite.
- SEC11: fresh runtime/dev/transitive/container/OS/actions/model-dependency scans on frozen graph with tool DB dates/skips/suppressions/exploitability and independent exception review.
- Full tenant matrix: owner/editor/reviewer/viewer/outsider/disabled/revoked/operator × projects/sources/files/jobs/memory/comments/reviews/exports/account lifecycle, including async execution/publication and restored access state.

No “security passed” from only empty static scan output; review filtered findings/metrics and business logic. Record exploitability preconditions, impact and residual risk; incident escalation if potential real data exposure is discovered.

## 6. Reliability, operations and compatibility

Run authorized full backend and supported browser/accessibility collections against frozen code. Record parameterized/subtest accounting separately, actual discovered cases, failures/errors/skips/blocked. Diagnose every prior failure and TEST-08 artifact discrepancy; retain original report and unique new report. Two required full browser runs green, no retry-masked unresolved flake.

Positive and negative engineering journeys from test plan; real isolated saved projects, not generic success mocks. Test simultaneous editing and background completion, history/archive/result freshness and export race; no caller permission bypass. Verify artifact compatibility/units/coordinates/elevations/dimensions/print scale in independent advertised target tools and versions; native unsupported formats remain unavailable, not passed.

Perform authorized DB+source/artifact restore to new environment, counts/hashes/references/role/session/job consistency, encryption/retention evidence, measured RTO/RPO, migration/concurrent-start/rollback failure rehearsal. Do not erase historical Aug8 evidence or infer it certifies new release.

Run approved S/M/L workload, repeat cycles, concurrency/soak/cancellation/backpressure. Measure latency/RSS/CPU/connections/DB/storage/throughput, no unbounded snapshot growth. Report tested limits and graceful unsupported rejection. Paid provider/cost measurements only if budget and data rights approved; otherwise NOT TESTED.

After explicit deployment approval only: confirm frontend/API/worker/config/image identity and authorized synthetic canary in existing hosting, enrollment/tenant/save/job/artifact/recovery controls. Local PASS alone cannot certify hosted release. No production stress or restore without separate controlled plan.

## 7. User and commercial verification

Independent engineer tasks with assistance/time/error/source-unit-scope comprehension and repeat-use metrics; no founder coaching substituting for unaided completion. Accessibility evaluated in actual primary stages and warning/export paths. Capture participant consent/qualifications and disclose sample limits.

If GateD in scope: provider sandbox full payment lifecycle, signature/idempotency/out-of-order webhooks, customer/org/seat identity, atomic quota reservations, failure/grace/refund/cancel/trial/tax policy and ledger reconciliation; raw card details never in Civora. New customer independently onboards, completes qualified task, obtains support, exports/deletes data per approved policies. No live charges simply to make audit look real.

Counsel/PE/IP/data-rights evidence actual dated review, not blank template or URL. Confirm customer ownership/retention/professional scope and incident/support owners. Investor evidence separates technical qualification from actual customer usage/retention/purchasing behavior; no valuation from code.

## 8. Issue closure ledger (required output schema)

For every original and newly discovered issue record:
- Original issue/audit section and classification/severity/priority.
- Original evidence/observed result and provenance/hash.
- Root cause / changed understanding, including corrections to original audit.
- Fix commit(s), child package and affected source/function/line.
- Approved semantic/engineering/security decision and compatibility policy.
- New regression test names/commands + independent expected source/tolerance.
- Frozen candidate/environment/engine/dependency/config/input/artifact identities.
- Current result PASS/PARTIAL/FAIL/NOT TESTED/UNKNOWN with counts and limitations.
- Independent review artifact/identity/competence/date and scope.
- Side effects, old-project compatibility and rollback/recovery evidence.
- Release-gate disposition, residual risk owner/expiry and next action.

Resolution vocabulary: Open; Implemented-awaiting-verification; Verified-within-scope; Contained-by-enforced-exclusion; Accepted-time-bound-risk; Not-reproduced-with-explanation; Superseded-by-linked-record. Never delete old issue; SEC10 remains CAN03 alias. “Not reproduced” requires direct investigation and does not mean a known failure was fixed.

## 9. Re-audit report and decision

Produce the original15-section report structure: executive summary; stage; architecture; feature inventory; engineering accuracy; canonical model; test reliability; security; UX; commercial readiness; investor diligence; blockers; prioritized remaining roadmap; next30/60/90 sequencing; final readiness answers. Evidence register distinguishes current code/current executed tests/historical/documents/founder/inference/environment. Include files/lines and current diagram.

Report discovered/executed/passed/failed/skipped/blocked and coverage ONLY if measured. Separate engineering functionality, engineering verification, reliability, security, usability, maintainability and commercial readiness. Stage6 needs documented correctness/reliability/operations for intended scope; Stage7/8 require external operational/customer evidence. Avoid global numerical rating or unsupported engineering-grade claim.

For each gate A–E quote objective criteria and evidence IDs, owner/reviewers and PASS/FAIL/NOT TESTED. Gate B cannot pass without scoped independent PE and recovery/identity/integrity evidence; C cannot pass without actual independent usability/security/operations/rights; D cannot pass on status-only billing. No waiver for wrong supported calculations or known tenant leakage. Unsupported claims visibly excluded and enforced.

Success means every51 baseline issue plus new issues has a traceable disposition, all required scoped tests freshly pass on frozen candidate, independent engineering/security/CAD/user evidence exists, legacy data preserved, and gate-specific human approval recorded. It does not mean all optional future disciplines implemented or the company has product-market fit.

## 10. Escalation and after-audit changes

Any changed code/dependency/schema/model/config/source fixture/standard after the acceptance freeze invalidates its affected evidence; release owner conducts documented impact analysis and reruns complete required acceptance for final release. No old SHA relabelling. New numerical discrepancy blocks affected output/release and opens ticket; suspected exposure invokes incident response without further unauthorized probing. Missing access/reviewer/budget is NOT TESTED, not permission to assume PASS. Final report must name remaining blockers and exact next verifiable action.

## 11. All-feature inventory reconciliation

Carry forward founder-directed complete capability inventory from P01/P20. Reconcile every route/control/flag/engine/provider/file/account/commercial mode against current source and observed results. Re-audit disabled/optional and newly added features in safe isolated modes; no unimplemented feature becomes “working” because a flag changed. Require real-vs-mock and enabled-vs-qualified distinctions and high-risk cross-feature interaction evidence. Compare original feature inventory to current inventory and explain every addition/removal/exclusion. A scoped release may pass while optional unavailable features remain explicitly unshipped; it cannot advertise their qualification.

