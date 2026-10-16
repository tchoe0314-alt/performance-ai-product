# Preserve explicit tailwater and its provenance

Parent `769a3f8d`; ENG-06 / CAN-01 follow-up. No release approval.

## Confirmed defect

`enrich_storm_production_depth` always derived tailwater from `target_outfall.z`.
An explicit hydraulic boundary could be overwritten by an unrelated geometric
elevation, and a verified-input source string was replaced by the generic selected
outfall label. Invalid explicit input could silently use that fallback instead.

Explicit `tailwater_elev_ft` now takes precedence, preserving finite positive,
zero and negative datum elevations and its source string. Missing source becomes
`provided_tailwater_unverified`, never invented verification. Explicit null,
nonfinite, boolean and malformed input cannot use outfall geometry as a substitute;
the returned elevation is null and backwater remains blocked on missing tailwater.
Original source input remains unchanged. No NaN/Infinity is emitted as that field.

Legacy outfall fallback is retained only when the explicit key is absent and is
marked `tailwater_input_validation.assumed_from_outfall`. This compatibility
assumption is NOT proof that a geometric outfall elevation is an accepted water
surface. Dataset/datum qualification and release-policy enforcement of accepted
boundary conditions remain required. No hydraulic formula/tolerance changed.

## Evidence

Guarded disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`;
no production/customer data, paid calls, external service or deployment.

- `results/tailwater-136.xml`:9 failed, reproducing loss/fallback/label defects.
- `results/tailwater-137.xml`: **48 passed**,21 dependency deprecation warnings,
  2.45s. Tailwater/profiles/producer regressions, result and export versions.
- `results/tailwater-depth-138.xml`: **16 passed / 2 failed**,21 dependency
  deprecation warnings,3.17s. The same pre-existing looped-water pressure/fire-flow
  expectations fail; not waived and not a clean broader suite.
- `git diff --check`:PASS. Failed evidence preserved; no expected number weakened.

Buildv13 retains prior results as historical/unverified until actual execution;
the version regression now includesv12. No persisted record migration or automatic
engineering recertification.

## Open scope / recovery

Qualified branched-network backwater, reference fixture/reviewer acceptance,
datum-compatible boundary evidence, legacy fallback release gates, and the six
earlier manual hydraulic failures remain open. This fix preserves evidence; it
does not certify the evidence or make the network solver complete.

Rollback requires review/revert of this isolated change; no schema migration.
Keep engine identifiers distinct and previous outputs historical. Reverting
reopens silently overwritten hydraulic inputs/provenance. No release gate passed.

Progress:0/5 release gates approved (0%), not coding completion.
