# Civora combined verification checkpoint

Status: preparation only. This is not a local, hosted, or professional acceptance result.

## Exact candidate and suite

- Candidate: `857b3f3918394dedfb610b59b0a51c9e438ec94e`.
- Branch at preparation: `codex/fix-can01-hydration`, clean working tree before this evidence-only commit.
- Standard suite: Acceptance v2 `2026-11-18.1`, 26 major cases. The 131 workflow families remain a coverage inventory, not 131 passes.
- Catalog SHA-256: `855a90e9e689ac7dd95b1678185b9705b3297203b210b37b4baedf778104900f`.
- Historical live baseline SHA-256: `652dacf2dd0d3b21e7fbedc7274c677645cdbb3bd6d0b73a15751bcdfb63a45f`.
- Frozen core fixture: building `office`, 169 × 85 ft → 179 × 85 ft; 14,365 → 15,215 sq ft; exact delta 850 sq ft. Storm pipe `SYN-STORM-PIPE-1`: 178.885 ft, 18 in, 1% slope, 90.0/88.21115 ft endpoint inverts, review-only.
- Performance gate remains 120,000 ms. The prior 138,574 ms observation is a failure baseline, not an adjusted target.

The historical `CORE_PASS_RUN_CARD_2026-11-21.md` remains pinned to `944ce345`; it must not be relabelled as evidence for this candidate. This checkpoint carries the replacement identity for the later run.

## Component provenance

This candidate contains frontend, API, worker, planner, and shared-domain changes. A later local run may use this one source revision for all components. A hosted run must record the actual frontend, API, and worker revisions independently; intentional split deployments are valid only when the exact matrix is declared and compatible.

Important integrated slices include:

- Authored geometry preservation and canonical propagation: `fc8c3e33`, `d75611bc`, `17e120b3`.
- Canvas responsiveness/navigation/starting actions: `d15dd81d`, `3c9f6b26`, `6105d3e8`, `63b947ab`, `4508e2fc`.
- Grading and takeoff truth: `8f9f468f`, `b19bac46`, `738332ed`, `cb8829ae` through `5f91074a`.
- Workflow/Review/Deliver truth: `ee9dd2bd`, `944ce345`.
- Chat switching and layout-preview independence: `145f581d`, `27e9e809`.
- Survey provenance, immutable evidence, review API/UI: `922790e4` through `69240a34`.
- Separate hosted component/worker identity checks: `f2bf822c`, `2644cf6b`, `e888720c`.
- Recalculation timing and checkpoint dependency integrity: `327906d2`, `8611914f`.
- Protected Storm generator-to-resolver identity: `2a50286f`, `857b3f39`.

## 22-item reconciliation

| Items | Current implementation status | Required next evidence |
| --- | --- | --- |
| 1 | Authored edit preservation is implemented and focused tests exist. | Combined local 169×85 → 179×85 save/reopen/recalculate/artifact agreement, then live. |
| 2 | Phase timing is implemented. The 138.574 s failure is not fixed or waived. | Combined instrumented run; optimize only the measured bottleneck, then repeat under 120 s. |
| 3–6 | Canvas navigation, compact controls, blank-canvas starts, and contextual next actions are integrated. | Desktop/narrow browser effects, persistence, accessibility, and blocked-state routing. |
| 7 | Survey provenance, units/CRS/datum/control blockers, immutable evidence, and reviewer decisions are implemented as review-only. | Combined import/reopen/replacement/permission checks; live address/provider checks separately. |
| 8 | Project-type/program preservation, preview invalidation, and parcel-boundary work are integrated. | Fresh supported site-type and irregular-parcel browser fixtures. |
| 9 | Existing/proposed/difference and no-data versus true-zero grading work is integrated. | Independent surface/volume comparison and stale-after-edit browser evidence. |
| 10 | Protected endpoint semantics and exact generator-to-resolver identity are implemented; ambiguity fails closed. | Combined feasible/infeasible network evidence plus hydraulic/reference checks. |
| 11–12 | Utility missing-measurement truth and dependency invalidation are implemented; broad discipline correctness is not inferred. | Reference fixtures and the connected canonical A/B run. |
| 13–15 | Review state truth, quantities/rate provenance, and drawing-only versus calculated export clarity are integrated. | Combined current/stale/failed/true-zero and actual-download checks. |
| 16 | Artifact revision/source checks and local parsers exist. | Inspect actual PDF/DXF/LandXML/JSON bytes from the same saved revision. |
| 17 | Native A/B handoff packet is prepared only. | Licensed Windows Civil 3D import/edit/update/reopen; external blocker. |
| 18 | Source-bound reviewer decisions exist. Password recovery sender and multi-account role evidence do not. | Approved sender, controlled inbox, and dedicated identities; external authorization/configuration. |
| 19 | Named targeting and chat project-switch persistence have focused coverage. | Combined browser A→B→A, preview/apply/cancel, timeout/unavailable-service checks. |
| 20 | Separate frontend/API/worker canary identities fail closed in code. | Hosted component receipts and disposable rollback/restore rehearsal. |
| 21 | Acceptance v2 and control inventory exist. | Execute all 26 cases without shrinking the denominator; reconcile visible controls. |
| 22 | No code result can establish customer value or commercial readiness. | Pilots and billing sandbox; external/business gate. |

## Confirmed remaining local implementation gap

`PERF-01` / item 2 is the only confirmed unclosed local product defect at this checkpoint. The connected authored-width workflow previously took 138,574 ms. Candidate timing now separates stage execution, checkpoint reconstruction/serialization, terminal packaging, and worker invocation time, while excluding approval wait, queue wait, browser polling, and network time. No optimization is claimed until the combined run identifies a substantive bottleneck and verifies a correctness-preserving change.

Everything else listed above is either prepared code awaiting combined evidence, a test gap, or an external prerequisite. An unrun case is not classified as a product defect.

## Prerequisites checked without running the suite

- Disk: approximately 6,000,000 KiB available on the candidate volume at preparation, above the prior 2 GiB headroom floor.
- Python: existing Python 3.11.15 environment at `civora-acceptance-worktree/.venv311`; no install is required. The focused Storm generator/resolver regression already executed against this candidate through that environment.
- Browser dependencies: existing `apps/web/node_modules` in `civora-acceptance-worktree` (about 619 MiB). The later run must use the documented external-runner configuration against this exact source, not silently build the acceptance worktree instead.
- Node: v25.8.2 available.
- Data: create a new labelled disposable storage directory outside existing `data`; never reuse or inspect customer/project storage.
- No server, browser, build, provider, or suite was launched for this checkpoint.

## Execution boundaries for the later run

**Combined local:** fixture/schema oracles; actual local frontend/API/worker; Setup/Generate/edit/recalculate/save/reopen; Review/quantities; PDF/DXF/LandXML byte inspection; stage timings; interruption/reconnect cases that are safe in disposable storage; focused control effects.

**Authenticated live:** exact alias and independent component revisions; production-session persistence and queue/approval behavior; live artifact endpoints; live responsiveness; safe public/mobile and supported provider behavior. No customer data or destructive/provider-paid case is implied.

**Native Civil 3D:** import, coordinates, units/elevations, supported object editability, A→B update, save/reopen. macOS LandXML parsing cannot pass this gate.

**Separately authorized release/operations:** push/deploy/promotion, provider cost, rollback/restore, SMTP recovery delivery, multi-account role changes, billing sandbox, and pilot activity.

## Go/no-go

**GO for one combined local acceptance run** on this exact candidate, using a fresh disposable store and the existing dependencies, provided the runner first confirms all three local components report `857b3f39…` and does not start a new install/build path unexpectedly.

**NO-GO for live release or an all-feature acceptance claim.** The 120-second performance failure remains open; native Civil 3D, live component receipts, recovery sender, multi-user authorization, rollback/restore, billing, and professional review remain separate gates.
