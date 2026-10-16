# Primitive takeoff validation and aggregate numeric safety

Parent `196bfaa2`; ENG-06 / TEST-02 follow-up. Not release acceptance.

## Reproduced defects and implementation

Rectangles/circles used permissive `_safe_float` plus clamping. Negative, NaN,
missing or malformed dimensions could become zero and still report success.
Linework coerced invalid coordinates or raised an unstructured indexing error.
Finite dimensions could multiply or accumulate into infinite successful totals.

New finite-number validation rejects booleans, missing/invalid/nonfinite values
and negative dimensions. Rectangles/circles validate computed area; polylines
validate point structure and coordinates and use stable length summation. Converted
geometry, aggregate areas/lengths/lot area and coverage ratios must stay finite.
Typed failures return empty totals. Unexpected implementation errors remain visible.
Zero dimensions/zero-length lines remain supported compatibility values; this is
not geometry-design approval. Numeric strings retain existing numeric compatibility.

No unit conversion, accepted valid formula or engineering design tolerance changed.
Engine buildv10 retains prior results as historical/unverified;v9 is included in
old-build regression. Recalculation, not rebind/migration, is required.

## Evidence

Guarded disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`;
no production/customer data, network, paid calls or deployment.

- `results/quantity-geometry-120.xml`:14 failed, original primitive failures.
- `results/quantity-geometry-121.xml`:166 passed before aggregate-overflow case.
- `results/quantity-overflow-122.xml`:1 failed, independent finite areas overflowing
  their combined total. Original reports preserved.
- `results/quantity-geometry-123.xml`: **167 passed**,21 dependency deprecation
  warnings,4.13s. Primitive/route/unit/polygon regressions, classification and
  coordination, phase truth/state/drainage, result/export versions, history,
  cost engine/workflows and dense utility benchmark.
- `results/quantity-planner-124.xml`: **15 passed / 6 failed**,21 dependency
  deprecation warnings,104.89s. This is NOT a clean integration result.
  Failures are manual quantity consistency/traceability expectations.
- Guarded planner diagnostics `quantity-diagnostic-125.log` / `126.log` locate
  the underlying error: conflicting route summary/segment lengths, not an invalid
  rectangle. Sample storm summary511.683ft disagrees with its published segments;
  utility summary152.5ft accompanies a stale101.5ft segment record.
  Producer/canonical projection repair is the next required work; assertions and
  strict reconciliation were not weakened. No working manual-flow claim is made.
- `git diff --check`:PASS.

## Limits and recovery

Stage-metadata validation before permissive max/default operations, source control,
all other engine families, professional reference acceptance and full browser/release
testing remain open. Invalid totals cannot be converted into approval by an empty
result or a changed test oracle. Warnings/defaults in unrelated modules are not
claimed remediated. Earlier persisted values are not automatically repaired.

Rollback:review/revert this isolated change; no schema migration. Retain build
identity distinctions and historical output. Reverting reopens invalid primitive
and overflow acceptance. No release gate passed.

Progress:0/5 release gates approved (0%), not coding completion.
