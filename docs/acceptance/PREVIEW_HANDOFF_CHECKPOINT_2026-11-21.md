# Preview handoff acceptance checkpoint

Candidate: `25b3177f472cf754ae75af9fd51cb0b6b2ef2458` plus the checkpoint-identity correction recorded with this evidence.

Suite: Acceptance v2 `2026-11-18.1` (26 major cases). This is a focused local-browser delta, not a new full-suite run and not live evidence.

## Proven focused assertions

- A saved synthetic checkpoint detail of about 7.45 MB produced a 705-byte project-bound `/api/preview` request. The request contained the project ID and render options, but no client `result` or `final_plan` copy.
- The browser rendered the returned preview image and the matching Storm review hold.
- Preview completion did not approve the checkpoint. One explicit Continue advanced it.
- A second Drainage checkpoint with a new input signature rendered a fresh Drainage hold and issued exactly one new compact preview request.
- The second checkpoint remained held until its own explicit Continue; it was not automatically approved.
- Job-list and job-detail polling did not overlap. Four saved-result reads covered initial hydration plus the two checkpoint transitions.
- A reproduced duplicate preview during project-to-job hydration was corrected by binding the checkpoint guard to workflow/calculation identity plus stage, rather than a changing project/job fallback.

## Cumulative 26-case ledger

The last complete live baseline remains the classification source. Focused local evidence below can improve a subcriterion without promoting an entire major case.

| Case | Major-case status | Current evidence / missing prerequisite |
| --- | --- | --- |
| AUTH-X | BLOCKED | Sign-in mechanics remain owner-excluded from this suite. |
| PUB-01 | FAIL (historical live) | Public Support routing requires a fresh live rerun; no public route was exercised here. |
| PRJ-01 | PARTIAL | Local create/save/reopen/copy/inaccessible-state checks exist; full access/archive matrix is incomplete. |
| DRAW-01 | PARTIAL | Core and advanced drawing persistence have focused local coverage; complete advertised layer/topology/control acceptance is not rerun here. |
| IMP-01 | PARTIAL | Synthetic survey/GeoJSON truth checks exist; CAD, oversize and duplicate-file behavior remain incomplete. |
| GEN-01 | FAIL (historical live) | The original requested-building omission still needs the exact fresh live fixture rerun on the candidate. |
| GEN-02 | PARTIAL | Irregular-boundary code/tests exist; fresh live containment evidence remains. |
| CAN-01 | PARTIAL | Authored geometry and propagation pass focused/local checks; full candidate-to-live revision chain remains. |
| GRADE-01 | PARTIAL | Signed depth and true-zero checks pass locally; independent accepted-surface/live evidence remains. |
| STORM-01 | PARTIAL | Protected identities/inverts and two explicit checkpoint transitions pass locally; full hydraulic/reference case remains. |
| UTIL-01 | PARTIAL | Missing measurements remain unknown and focused utility truth passes; full connected reference fixture remains. |
| QTY-01 | PARTIAL | Local grading/takeoff agreement is covered; full live current-revision takeoff remains. |
| REV-01 | PARTIAL | Current/stale navigation and the two authoritative review holds have local browser evidence; full live failed/historical matrix remains. |
| DEL-01 | PARTIAL | Local current/stale gating and artifact checks exist; full released-revision download set remains. |
| CHAT-01 | PARTIAL | Named targeting and project-switch persistence have focused tests; provider/session/timeout matrix remains. |
| COLLAB-01 | BLOCKED | Requires a second approved synthetic identity and role/revocation setup. |
| UX-01 | PARTIAL | Compact canvas controls and focused navigation checks exist; complete visible-control reconciliation remains. |
| UX-02 | PARTIAL | Public/narrow responsive checks exist; authenticated full workspace matrix remains. |
| PERF-01 | PARTIAL | One authored recalculation completed in 104.009 s under the 120 s gate. This preview check proves 705-byte handoffs, not total runtime or p50/p95. |
| REL-01 | PARTIAL | Save-conflict recovery, bounded polling, compact previews and stage-freshness pass locally; interruption/network/retry matrix remains. |
| SEC-01 | BLOCKED | Requires approved multi-identity authorization and worker/artifact receipts. |
| OPS-01 | BLOCKED | Requires isolated hosted rollback/restore and exact component receipts. |
| DATA-01 | BLOCKED | Requires a dedicated lifecycle identity, retention criteria and deletion confirmation. |
| BILL-01 | BLOCKED | Billing remains deferred and requires provider sandbox instruments. |
| C3D-01 | BLOCKED | Requires licensed Windows Civil 3D native import/edit/update testing. |
| PE-01 | BLOCKED | Requires adopted criteria, complete inputs and licensed-engineer review. |

Major-case totals are therefore unchanged by this focused delta: **0 full PASS, 2 historical FAIL, 14 PARTIAL, 10 BLOCKED**. There are no `NOT_RUN` case labels, but many individual criteria remain unexecuted as listed.

## Local case results versus historical live status

The aggregate above is the last complete **live** classification. It must not erase later, narrower local case results, and those local results must not be presented as live acceptance:

- `PRJ-01`: local synthetic case PASS at `d1cdc517` for project duplication and inaccessible-project state clearing. Archive/role/live coverage remains outside that local scope.
- `REV-01`: local focused case PASS at product `ed10548c` with acceptance alignment recorded at `e1252f00`; it covers Review navigation/currentness and normal local downloads, not every hosted failure/history state.
- `UX-01`: local focused case PASS at `e1252f00` for the card's desktop interaction/navigation assertions. Full live control inventory and supported-browser coverage remain separate.
- `GEN-01`: local focused PASS on the descendant of `05d6407c` recorded by the subsequent commits. A genuinely blank Industrial project generated one 14,400-sf Industrial review building and a 48-stall parking concept, preserved `industrial_site` through the real worker, and stopped at an explicit Layout approval. The prior live GEN-01 failure remains historical until this exact case runs live.

The first GEN-01 run truthfully exposed an invalid generated placement: building `[216,88]–[396,168]` overlapped parking `[96,72]–[348,184]` by 132 × 80 ft. The corrected generator places the same building at `[372,88]–[552,168]`, leaving 24 ft to the parking court. The unchanged validator now reports Layout complete and still rejects the original overlap in a focused adverse test. A subsequent parcel matrix preserves the exact 14,400-sf request on 600×400, 500×300 and 1,000×700-ft parcels, keeps each concept inside the parcel and leaves authored buildings untouched. On an intentionally tight 240×180-ft parcel, the generator omits the unfit building instead of shrinking or crossing the boundary; the validator independently rejects the forced out-of-bounds rectangle. Generated objects remain review-only. This is not engineering acceptance and it does not make downstream grading, drainage, utilities, Review, or Deliver pass.

## Next distinct case

The highest-value distinct next case is **GEN-02**: activate a fresh concave parcel through the supported imported-boundary path, then verify generated concepts remain inside its true notched geometry after save/reopen. That extends containment evidence beyond rectangular bounds without repeating GEN-01 or requiring native Civil 3D, billing, or account changes.
