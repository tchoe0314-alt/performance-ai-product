# Route length evidence and units

Parent `aebca1ba`; ENG-06 / EXP-03 follow-up, not release acceptance.

## Confirmed defects

Storm/utility takeoff used `length_ft or coordinate_length`. Explicit zero fell
through to a different measurement; route geometry in metres could be labeled
feet. Negative/nonfinite/bool lengths were not rejected by a safe engine contract.

Shared `_route_length_ft` now preserves explicit finite nonnegative `length_ft`,
including zero, without converting it again. Geometry fallback requires finite
x/y points and explicit segment feet/metre units for non-foot drawings. Metres
convert by the exact international-foot factor. Unknown units and invalid evidence
produce a structured failure with empty totals, including direct `QuantityEngine`
calls. Only the typed input error is caught; unexpected programming errors are not
silently converted. Complete explicit zero segment totals override drawing proxies.

Compatibility: unlabeled paths in legacy foot drawings retain feet; source-ID-only
stage records without lengths/paths retain their existing drawing fallback.
No persisted input is changed. Stage summaries still have existing precedence;
conflicting summary/segment measurements are not newly reconciled by this repair.

## Evidence

Guarded disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`.
No production/customer data, network, paid API calls or deployment.

- `results/route-114.xml`:14 failed/4 passed, original errors preserved.
- `results/route-115.xml`:131 passed before additional negative/domain cases.
- `results/route-116.xml`: **137 passed**,21 dependency deprecation warnings,3.58s.
  Covers route/drawing/polygon units, classification/coordination, phase truth/state,
  drainage, canonical/export versions, history, cost engine and cost workflows.
- `git diff --check`:PASS. Not full-suite/browser/PostgreSQL or PE acceptance.

Expected geometry case:3.048m =10ft; explicit10ft stays10ft even in a metric
drawing. Explicit0ft stays0 despite a100-unit route or drawing proxy. Invalid
coordinates/units/negative/nonfinite/bool lengths cannot produce successful totals.

Engine revisionv8 marks older builds unverified without deleting or recertifying
history. The priorv7 is added to explicit historical-build tests.

## Open scope and rollback

Parent-stage unit inheritance, mixed-source metadata contracts, summary/segment
consistency, source-ID-only missing measurements, survey feet, full unit/datum and
independent reference review remain open. Legacy assumptions are compatibility,
not proof of engineering units or surveyed accuracy. No release gate passed.

Review/revert this isolated commit if needed; no migration rollback. Do not reuse
v8 for the old algorithm or promote historical outputs. Reverting reopens zero
fallback and ambiguous route-unit calculations.

Progress:0/5 release gates approved (0%), not a coding-completion estimate.
