# Partial terrain is missing evidence

Parent: `8878f846`. Engineering missing-data/estimated-value distinction.

Confirmed path: build_terrain_surface recorded failed samples as NaN, returned
the partial grid when any sample succeeded, and grading_support immediately
called normalize_surface, which substituted the mean elevation into missing
cells. Those elevations were not observed data.

Repair: the provider returns None if any sample is unavailable. A partial grid
cannot reach that caller's mean-fill step. Completely sampled terrain remains
unchanged. Existing grading fallback behavior remains explicitly outside this
repair; it must not be represented as survey or complete provider evidence.
No stored terrain/results, source history, units or numerical formulas changed.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/terrain-48.xml`:
13 tests+13 subtests passed, covering tile/transport boundaries and new synthetic
2x2 all-valid/one-missing surface cases. The expected missing case is None, not
a Civora-computed substitute value. Valid pixel decoding is only a compatibility
check, not an independent engineering oracle. No provider network, actual token,
production/customer data, paid services or deployment used.

Open: public terrain vertical units/datum through grading, explicit user-facing
unavailable-terrain diagnostics, inferred fallback release gates, tile/request
budgets and independent control data. normalize_surface remains a legacy helper;
this change closes its partial-tile entry path, not every possible caller or
source of missing values. No engineering/release gate is declared complete.

Rollback: revert this isolated commit without data migration. Reverting would
restore hidden mean-filled provider gaps and is not an acceptable accuracy fix.
