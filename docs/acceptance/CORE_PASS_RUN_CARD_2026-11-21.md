# Civora core acceptance run card

Status: preparation only, pinned to the pre-survey-integration product revision below. This document does not record a test run or live acceptance. A later integration candidate must replace the component identities in its run evidence rather than treating this historical pin as current.

## Sources and identity

- Candidate: `944ce3455c9d18db7cbe88c35867d66bbd8da84e`.
- Coordinated candidate expectation: frontend, API, and worker must each identify this exact revision before results count against the candidate. A deliberately split deployment requires its own explicit component matrix; equality must not be inferred from one health endpoint.
- Standard suite: Acceptance v2 `2026-11-18.1`, 26 major cases. Its catalog cross-checks the historical 131 workflow families; 131 is an inventory denominator, not a pass count.
- Frozen source hashes are recorded in `core-pass-2026-11-21.json`. Live component identities must be captured again at run time.

## First core pass

Use one uniquely labelled disposable project and the frozen A/B fixture. Do not substitute a similarly named historical project.

| Order | Cases | Action and independent expected result | Execution boundary |
| --- | --- | --- | --- |
| 1 | PRJ-01, GEN-01 | Create/open the fixture; confirm building `office` is exactly 169 × 85 ft and 14,365 sq ft before generation. Generate must preserve the explicit program and saved type. | Local deterministic browser or authenticated live browser; generation requires API and worker. |
| 2 | DRAW-01, CAN-01 | Edit only width 169 → 179 ft; save and reopen. Canonical geometry must be 179 × 85 ft. Untouched generated objects may refresh, but the authored building must not revert. | Local deterministic browser or authenticated live browser. |
| 3 | CAN-01, QTY-01, REV-01 | Recalculate the affected dependency closure with normal approvals. Current quantity must be 15,215 sq ft, exactly +850 sq ft. Review must move stale → current only for the same saved revision. | API and worker required; no external AI/provider is part of the fixture. |
| 4 | DEL-01 | Download actual PDF, DXF, and LandXML bytes. PDF/DXF must represent the revised building. LandXML must retain `SYN-STORM-PIPE-1`, ordered endpoints, 178.885 ft, 18 in, 1% slope, 90.0/88.21115 ft inverts, and review-only flags. All artifacts must identify or be bound to the same current saved calculation revision. | Browser plus API/worker artifact endpoints. Native Civil 3D is not implied. |
| 5 | PERF-01, REL-01 | Record startup, approval waiting, worker stages, final persistence, reload, and download time separately. Terminal job completion must remain within the existing 120,000 ms gate. The prior 138,574 ms observation is a failed baseline, not a relaxed limit. | Repeatable instrumented browser and worker receipts required. |

Continue independent assertions after a failure. Record `PASS`, `FAIL`, `BLOCKED`, or `NOT_RUN` per case; never turn an unreached downstream step into a pass.

## What can run without cloud services

- Fixture arithmetic and schema check: `node scripts/check_core_acceptance_fixture.cjs`.
- Pure canonical serialization, edit preservation, dependency invalidation, Review/Deliver truth-copy, chat switch, takeoff, grading, and layout-preview contracts using installed local dependencies.
- PDF/DXF/LandXML parsers against already produced disposable artifacts.
- A full deterministic local browser path only when the local API, worker, disposable storage, and already-installed dependencies are available; it is local evidence, not live acceptance.

## What needs authenticated browser or provider access

- Live alias plus exact frontend/API/worker identity and revision receipts.
- Production-session save/reopen, job queue, approval checkpoints, artifact download, reconnect, and measured live performance.
- Deployment/rollback evidence and any hosted health/canary receipt.
- Password-recovery delivery requires an approved sender and controlled inbox; code presence alone is insufficient.

## Separately blocked prerequisites

- Storm backend dependency check: the integrated source and frontend contracts are present, but this checkout has no compatible dependency-complete Python 3.11 environment. The generator-to-resolver authored-identity path must be rerun in a dependency-complete environment before acceptance.
- Native Civil 3D: requires supported licensed Windows Civil 3D to import, inspect, edit, update, and reopen the A/B artifacts. LandXML parsing on macOS is not this gate.
- Account recovery: requires approved SMTP/provider configuration and controlled delivery/expiry testing. No sender is approved in this candidate evidence.
- Professional engineering approval, billing, multi-user authorization, backup/restore, and paid-pilot readiness remain their own Acceptance v2 cases and are not covered by the first core pass.
