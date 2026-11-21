# Survey-control upload gap

Status: confirmed product gap on integration candidate `33005d7d`. This is not a live acceptance result.

## What exists

- Setup exposes one **Upload Survey** action through `SetupSurveyTerrainSection`.
- The action sends one supported existing-conditions file to `POST /api/upload-existing-conditions`.
- Imported coordinates, units, CRS, horizontal/vertical datum, embedded control metadata, eligibility, and exact blockers are persisted and shown after reopen.
- The importer can preserve a control package already embedded in a supported source. It does not infer missing control, datum, or verification.

## What does not exist

There is no distinct user-facing, authorized survey-control package workflow that:

1. identifies the survey/control artifact separately from general context data;
2. records the qualified verifier and verification authority;
3. binds benchmark ID/elevation, CRS, horizontal and vertical datum, units, artifact hash, and attestation to the saved project;
4. lets an authorized reviewer accept or reject that immutable package; and
5. records an auditable acceptance event before `control_verified` may become true.

Typing datum, units, or benchmark text is therefore not verification. A general source upload may carry embedded evidence for review, but Civora must keep grading eligibility blocked unless the imported package already contains trustworthy explicit verification. The current UI correctly surfaces that blocker; it does not provide the missing authorization step.

## Required acceptance evidence

- A dedicated synthetic control artifact with distinct benchmark and datum values.
- Allowed-role upload and approval, plus viewer/unauthorized rejection.
- Save/reopen preserving artifact identity, hash, verifier, and decision.
- Replacement and revocation invalidating affected grading results without modifying unrelated project data.
- Review and Deliver reporting the accepted control revision or the exact blocker.

Until that workflow exists and is tested, survey imports are review context unless their source already carries accepted, auditable control evidence. This gap must not be papered over by setting `control_verified` from ordinary typed fields.
