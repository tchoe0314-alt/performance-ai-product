# Calculation identity and compatibility protection

Calculation execution now records `engineering_core_2026_10_v2`; saving,
viewing, importing or binding an old result does not grant that identity.
Matching-input results without current identity are retained as archived history,
not silently activated. Calculated exports block stale/unverified results.
An actual orchestration run stamps both result and derived-plan metadata.

A partial rerun inheriting a checkpoint without current method identity remains
unverified and requires a full run; it cannot certify old inherited disciplines
merely because one new stage executed. Current-method checkpoints retain the
partial workflow. A method stamp describes execution, not independent accuracy.

Existing test fixtures explicitly representing completed calculations now carry
the method identity. New negative cases retain unstamped/obsolete results,
verify archive-only persistence without active-state replacement, check exports
reject unstamped engineering output, and prove partial execution cannot refresh
legacy checkpoint identity. Geometry-compatibility expectations are unchanged.

Fresh isolated result/history/atomic-export/LandXML/artifact run:85 PASS,
21 dependency deprecation warnings, no skips. Report:
`/tmp/civora-repair-verification.NBAOtD/results/version-16.xml`.

No existing result/data migration was executed. After eventual deployment,
older results remain history and need recalculation for current calculated
exports. Drawing-only snapshot export is a separate scope. Rollback must keep
equivalent freshness/version gating, not reactivate old-method results.
Full release regression and independent numerical validation remain required.
