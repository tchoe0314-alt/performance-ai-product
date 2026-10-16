# Enclosed polygon quantity areas

Parent `24b59472`. ENG-06 / TEST-02 follow-up; not engineering-grade certification.

## Reproduced failure and independent oracles

`QuantityEngine.compute` used `_bbox_area_from_polygon` for polygon actions.
It reported a 10-by-10 right triangle as100sf rather than50sf; an L shape
enclosing two10-by-2 strips minus their2-by-2 overlap as100sf rather than36sf;
and a diagonal diamond as100sf rather than50sf. These expected areas are
analytical, not derived from the implementation. Reversing or explicitly closing
the rings preserves their true area. A translated triangle checks coordinate-offset
invariance. Invalid/self-intersecting/degenerate/nonfinite rings cannot qualify.

The new function uses the existing Shapely dependency to validate a single simple
planar ring and compute its enclosed area. It does not infer hole topology, repair
self-intersections or coerce malformed coordinates tozero. Invalid polygons yield
a structured failed quantity result with no partial totals. Existing rectangle,
circle, length classification and source trace logic are unchanged.

## Result compatibility

Engine build is now `engineering_core_2026_10_v6`. Older takeoffs are retained but
unverified, not recertified by save/rebind/view. Explicit version regression adds
v5 to retained historical cases and requires actual execution to stamp v6.
This remains a coarse whole-build invalidation; per-engine manifests are open.

## Isolated evidence

Source/SQLite copy under `/tmp/civora-repair-verification.NBAOtD` with Python
write/network/subprocess guard. No customer data, production, paid calls or deploys.

- `results/quantity-104.xml`:18 failed, preserving the original area/domain defects.
- `results/quantity-105.xml`:29 passed,21 dependency deprecation warnings,1.02s.
- `results/quantity-version-106.xml`:60 passed/3 failed,108.08s. Failures asserted
  the now-obsolete v5 build label; updated to v6 while adding old-v5 invalidation.
- `results/quantity-final-107.xml`: **98 passed**, 21 dependency deprecation
  warnings, 108.45s. Includes all new polygon cases, classification/coordination,
  phase truth/state/drainage checks, canonical result/export versions, calculation
  history, manual validation, phase exit and dense-utility benchmark tests.
- `git diff --check`:PASS. Not a fresh full-suite/browser or independent PE review.

## Risks, limits and rollback

Corrected polygon quantities can lower cost/impervious totals; rerun dependent
calculations instead of migrating or relabeling old numbers. Single planar ring
support is not a general multipart/holes/geodesic takeoff method. Full metric and
metadata-unit handling, overlapping-object semantics, standards/PE/reference review,
and complete browser/export qualification remain open. No release gate passed.

Rollback requires review/revert of this isolated change; no schema migration.
Do not reuse the v6 identifier for the old bounding-box algorithm. Reverting must
retain explicit provenance and block old/incorrect results from current claims.

## Progress accounting

Release acceptance:0 of5 gates approved (0%). This is not an estimate of coding
completion. Passing scoped tests cannot establish the share of all engineering,
security, commercial and independent-evidence work completed.
