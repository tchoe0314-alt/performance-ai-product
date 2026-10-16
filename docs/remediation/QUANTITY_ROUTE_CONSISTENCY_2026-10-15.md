# Reconcile route summaries with measured segments

Parent `10094974`; ENG-06 / CAN-01 follow-up. No release gate passed.

## Reproduced defect

Storm quantities preferred the first positive summary; utilities selected the
maximum. Both allowed a100ft summary to override10ft of measured segments without
reporting inconsistent evidence. Explicit summaryzero also fell through. Invalid
negative/nonfinite summaries were accepted or ignored rather than rejected.

`_reconciled_route_total` validates explicit summaries and all available segment
measurements using the existing route contract. Summary, stats and complete
segment totals must agree at the existing three-decimal reporting precision;
otherwise a typed input error returns failure with no partial quantities. Stable
summation handles0.1+0.2 without a false conflict. This is data consistency, not
a professional design tolerance or a source-accuracy claim.

Consistent explicitzero remains authoritative. Incomplete source-ID-only segment
records cannot independently certify the aggregate; the existing drawing fallback
remains when no complete measurement or explicit summary exists. This repair does
not fabricate missing segment lengths or reconcile intentionally different scopes.
Producers with different scopes must supply separately named/typed quantities,
not conflicting values for the same metric.

## Isolated evidence

Disposable source/SQLite with write/network/subprocess guard under
`/tmp/civora-repair-verification.NBAOtD`. No production/customer data, paid calls
or deployment; original reports unchanged.

- `results/route-consistency-117.xml`:10 failed/2 passed, reproduced contradictions.
- `results/route-consistency-118.xml`: **150 passed**,21 dependency deprecation
  warnings,3.87s. Consistency/units/polygons, classification/coordination, phase
  truth/state/drainage, result/export versions/history and cost consumers.
- `results/route-dense-119.xml`: **1 passed**,0.57s, dense utility benchmark.
- These suites do not overlap (151 cases). `git diff --check`:PASS.
- Not a fresh full-suite/browser/PostgreSQL or independent engineering certificate.

Buildv9 marks older results unverified without deleting them. Tests retainv2-v8
as historical and require execution for the current stamp; expected engineering
numbers were not changed to match bad behavior.

## Open risks and recovery

Incomplete measurements, per-stage unit inheritance, producer scope conventions,
other quantity families and independent PE/reference review remain open. Summary
fields rounded differently upstream can now block a takeoff, intentionally exposing
the inconsistency for producer-level correction rather than increasing tolerance.
Do not widen comparisons merely to pass fixtures.

Rollback:review/revert this isolated commit; no schema migration. Keep numerical
build identity distinct and old outputs historical. Reverting reopens silent
selection among contradictory values. No persisted result repair performed.

Progress:0/5 release gates approved (0%), not coding completion.
