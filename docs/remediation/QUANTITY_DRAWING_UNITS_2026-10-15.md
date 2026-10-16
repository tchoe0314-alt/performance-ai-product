# Drawing units at the quantity boundary

Parent `f1638cd8`. ENG-06 / EXP-03 follow-up. No release gate closure.

## Reproduction and contract

The quantity engine labeled drawing measures as square feet/feet without reading
drawing units. A3.048m by6.096m building was18.581sf instead of200sf. Independent
oracles use the exact international-foot definition:1ft =0.3048m.

Drawing-derived rectangle/circle/polygon areas, line lengths and lot rectangle
area now convert before imperial aggregation, parking/default-width calculations
and comparison with stage summaries. Explicit `_sf`, `_ft` and `_cy` metadata is
not converted again. Supported labels:ft/foot/feet andm/meter(s)/metre(s).
Explicit unknown/null/nonstring units fail with empty totals. Missing legacy units
retain feet; `explain.meta_summary.legacy_units_assumed` records this compatibility
assumption. Explanation also exposes the conversion and quantity output units.

Engine revision isv7. Older output is retained/unverified and requires actual
recalculation, not rebind or migration recertification. v6 is added to historical
version checks. No stored schema migration or source-data mutation.

## Evidence

Reports in `/tmp/civora-repair-verification.NBAOtD/results/` from disposable source
and SQLite with write/network/subprocess guard; no production/customer data or paid calls.

- `quantity-units-108.xml`:10 failed/1 passed; original unit defects preserved.
- `quantity-units-109.xml`:88 passed before added shape/explanation cases.
- `quantity-units-110.xml`:91 passed/1 failed; sidewalk fixture incorrectly claimed
  building identity. Corrected fixture identity; preserved report.
- `quantity-units-111.xml`:91 passed/1 failed; unsupported SIDEWALK layer in new
  fixture. The existing canonical takeoff layer isWALK; changed fixture to that
  actual contract without altering its10ft oracle. Classification expansion is
  separate work, not silently claimed fixed.
- `quantity-units-112.xml`: **92 passed**,21 dependency deprecation warnings,2.03s.
  Unit cases, polygon regressions, classification/coordination, truth/state/drainage,
  canonical/result/export versions and calculation-history tests.
- `quantity-cost-113.xml`: **20 passed**,21 dependency deprecation warnings,2.13s;
  cost-engine and application cost workflows. Non-overlapping with112 (112 cases total).
- `git diff --check`:PASS. Not a current full-suite/browser/PE certificate.

## Remaining risks / rollback

Unlabeled stage route-point fallbacks, per-object mixed units, survey-foot labels,
geographic/geodesic geometry and full finite/domain validation require separate
qualification. This change does not infer units for those records. All-engine
unit/datum consistency, external CAD and independent engineering review remain open.
Default-foot legacy behavior must never be represented as surveyed control.

Corrected quantities may change derived costs/impervious estimates. Rerun rather
than modify historical values. Revert only with review; no schema rollback needed.
Do not reusev7 for the old unconverted algorithm or promote old results as current.

Progress:0/5 release gates approved (0%). This measures approved release evidence,
not coding effort or a percentage of engineering correctness.
