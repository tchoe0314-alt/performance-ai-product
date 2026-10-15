# Water sizing pressure paths

Parent: `919b89cc`. ENG-06/Q13 pressure bookkeeping defect.

Confirmed: each segment's residual subtracted only its own losses from supply
pressure, omitting upstream friction/static losses. The aggregate instead summed
all segments, incorrectly placing parallel branches in series. The validated
supply forest now propagates pressure from each source root to its descendants.
Fixed meter/backflow/hot-water losses apply once per source path; each segment
subtracts its friction and existing uphill static loss, stores its endpoint
residual, and passes unrounded pressure onward. Aggregate remaining pressure is
the minimum endpoint residual, not the sum of unrelated branch losses.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/water-73.xml`:59 tests passed.
New controlled-loss test fixes5psi/100ft independent of pipe selection:60psi
source minus13 fixed gives47; main5 loss gives42, branches2/3 give40/39, minimum39.
All six segment permutations agree, and public sizing does not mutate input
segments. Serial friction/static arithmetic requires50.67 then46.505psi.
Separate EPA formula/unit, input/domain, topology/demand and engine contracts pass.
No provider, production/customer data, paid service, deployment or migrations.

Remaining: downhill static-pressure sign (currently conservative clamp), demand
curve/standards, required fixture-pressure acceptance, looped/multi-source solver,
independent PE/reference qualification and final candidate build identity.
This does not certify complete water design. Existing saved calculations remain
unchanged. Rollback is an isolated code revert, no schema rollback; it restores
misleading downstream/aggregate pressures and must not recertify old results.
