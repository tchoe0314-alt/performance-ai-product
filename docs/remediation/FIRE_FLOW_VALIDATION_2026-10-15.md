# Fire-flow request and pipe identity validation

Parent: `c89553ea`. ENG-06/Q14 fire-flow search correctness.

Confirmed defects: entry-point search parameters lacked finite/domain checks;
unnamed pipes were generated as W-index during shortest-path lookup but used
blank identity while adding fire demand. Such pipes could receive no added flow
and appear to support the search ceiling without corresponding pressure loss.

Fire-flow now validates finite/domain-safe pressures, flow targets, roughness,
static coefficient, search bounds/tolerance and hydrant identity. It normalizes
pipe identities once, rejects duplicates and preflights the complete supported
pressure-tree before search. Path and demand assignment use the same identities.
Invalid input returns valid=false and unknown capacity/pressure, not invented0
or NaN. Explicit zero base flow no longer falls through a conflicting alias.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/water-77.xml`:78 tests passed.
New invalid request cases require finite-JSON failure outputs with no capacity;
unnamed pipe receives W-1 in both paths, has positive modeled fire flow matching
reported available flow, and no longer reports the5000GPM search ceiling for the
synthetic2inch pipe. Duplicate IDs reject. Existing water/hydraulic/engine tests
pass. No real provider, production/customer data, deployment or paid services.

Remaining: calibrated/reference fire-flow benchmarks, bounded-search convergence
certificates, downstream production-depth projection, full solver/standards/PE
acceptance and final method invalidation. This is not hydrant certification or
support for loops/multiple sources. Existing saved outputs unchanged. Rollback
requires preserving history and explicitly unverified old results; reverting
alone restores missing-demand capacity risk. No schema migration required.
