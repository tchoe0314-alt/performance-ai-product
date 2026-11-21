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
| IMP-01 | PARTIAL | Synthetic survey/GeoJSON truth, duplicate, unsupported, size-limit and interior-ring safeguards pass locally; CAD fidelity remains incomplete. |
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
| REL-01 | PARTIAL | Upload/save faults and one active-job disconnect/reconnect recover safely with stable identity and approval; broader interruption/retry matrix remains. |
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

GEN-02 now has a focused local delta. The normal import/apply action preserved a five-vertex concave boundary, its projected feet/CRS provenance and stale-system invalidation through save/reopen in a 7.1-second disposable browser check. A deterministic 684,000-sf parcel with a 200×80-ft indentation kept the full 14,400-sf Industrial review program and all generated review geometry inside the canonical polygon; generation repositioned a water corridor that formerly crossed the notch. A deeper notch is rejected by the actual layout validator even though its rectangular bounds contain the building. A narrow-L parcel that cannot contain the requested program returns an explicit Generate blocker and does not start calculation or publish a partial concept set as ready. This is local synthetic evidence, not a survey, live, or professional acceptance claim.

IMP-01 adverse recovery now has a focused local browser pass. Re-importing byte-identical GeoJSON leaves the saved project input and survey-control review state unchanged and says the source is already active. A PDF selected through the ordinary upload control is rejected as unsupported without a request or saved-state change. With the documented existing-conditions limit configured to 1 MiB, a 1 MiB-plus synthetic GeoJSON receives the exact maximum-size message and preserves the last valid source. TXT remains an advertised input type: arbitrary TXT is stored immutably as a failed metadata-only review source, not misclassified as an unsupported extension, and it cannot replace the active project source. CAD fidelity, duplicate-file storage lifecycle and production-size/load behavior remain outside this focused pass.

An exact projected-feet Polygon fixture also proves the interior-ring boundary. The backend import was given CRS/units through its documented coordinate-system argument rather than a non-standard embedded projected GeoJSON `crs`; it preserved the 600×400-ft exterior and 40×80-ft exclusion verbatim, with a net 236,800-sf area. The frontend refuses to flatten that exclusion into the active one-ring site boundary and gives the explicit engineering-review message. The adverse corridor crosses 800 sf of the exclusion even though all four corridor corners lie outside the hole, demonstrating why exterior-only corner checks are insufficient. Hole-aware active boundaries remain unsupported; the safe behavior is explicit rejection with the current boundary unchanged.

REL-01 now has a focused ordinary-upload recovery pass in the same disposable browser flow. A connection-reset upload reports backend attention and leaves the saved project byte-identical. A valid upload followed by two deterministic 409 project-save responses reports that the source was not applied and again leaves the saved input unchanged. Removing the fault and retrying once saves the new source normally. The check used the normal upload and save hooks and authoritative backend reads, not direct client-state assertions. It proves project-state convergence, not immutable-upload storage deduplication or recovery of a running engineering calculation.

The running-calculation reconnect slice initially reproduced a real failure: the backend reached and retained the Layout approval hold, but reloading after a controlled browser disconnect cleared the freshly restored job list and the Generate panel said no run had started. Authentication restore now performs one forced server job refresh, and project workspace reset retains the account's server-owned job summaries while clearing only the active/selected UI pointers. The rerun restored the same job ID and authoritative Layout hold, required the same explicit Continue action, retained the saved Industrial type and 14,400-sf/48-stall program, and observed exactly one orchestration request, zero continuation requests and zero export requests. This is one focused local disconnect/reconnect transition, not a broad network or worker-restart certification.

The earlier broad TypeScript check remains independently red and is not waived by these focused passes. Its concrete categories are a `PreviewRequestPayload.preview_mode` narrowing error in `PerformanceAIDashboardView`, legacy fixture typing in `generate-program-preservation`, optional slope assertions in `phase1-dependency-graph-contract`, and stale preview/result payload shapes in `result-hydration-polling-contract`. A first attempt without a local dependency link also produced dependency-resolution noise; the linked-dependency rerun above is the meaningful list. None of those errors originated in the IMP-01 files, whose targeted ESLint check passes. They require a separate bounded correction pass rather than being hidden in import acceptance.

## Next distinct case

The highest-value distinct next reliability slice is worker/process restart recovery at a saved checkpoint, including stale-revision refusal and retry/cancel behavior. Server-side retention of byte-identical immutable upload files still needs an explicit lifecycle policy; the completed import pass proves project idempotency, not storage deduplication.
