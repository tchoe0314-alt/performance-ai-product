# Survey-control upload gap

Status: historical gap recorded on `33005d7d`; partially addressed in code through candidate `857b3f39`. This is not a local or live acceptance result.

The current candidate now stores a server-owned immutable source ID and digest,
binds it to the owning project, and lets an existing project reviewer record an
accept/reject decision against that exact source. Replacement, stale, missing,
and cross-project evidence fail closed, and the UI shows the server-recorded
decision. That decision remains review-only and does not certify survey control
or unlock grading/construction use.

## What exists

- Setup exposes one **Upload Survey** action through `SetupSurveyTerrainSection`.
- The action sends one supported existing-conditions file to `POST /api/upload-existing-conditions`.
- Imported coordinates, units, CRS, horizontal/vertical datum, embedded control metadata, eligibility, and exact blockers are persisted and shown after reopen.
- The importer can preserve a control package already embedded in a supported source. It does not infer missing control, datum, or verification.

## What still does not exist

There is no qualified survey-control acceptance workflow that:

1. identifies the survey/control artifact separately from general context data;
2. records the qualified verifier and verification authority;
3. binds benchmark ID/elevation, CRS, horizontal and vertical datum, units, artifact hash, and attestation to the saved project;
4. establishes that the reviewer has the required survey-control verification authority, not only ordinary project-review permission; and
5. records the separately accepted engineering-control revision before `control_verified` may become true.

Typing datum, units, or benchmark text is therefore not verification. A general source upload may carry embedded evidence for review, but Civora must keep grading eligibility blocked unless the imported package already contains trustworthy explicit verification. The current UI correctly surfaces that blocker and records project review; it does not invent the missing professional authorization or certification step.

## Required acceptance evidence

- A dedicated synthetic control artifact with distinct benchmark and datum values.
- Allowed-role upload and approval, plus viewer/unauthorized rejection.
- Save/reopen preserving artifact identity, hash, verifier, and decision.
- Replacement and revocation invalidating affected grading results without modifying unrelated project data.
- Review and Deliver reporting the accepted control revision or the exact blocker.

Until that workflow exists and is tested, survey imports are review context unless their source already carries accepted, auditable control evidence. This gap must not be papered over by setting `control_verified` from ordinary typed fields.
