# Water fixture-demand dependency repair

Parent: `fbe6abff`. ENG-06/Q13 deterministic demand propagation.

Confirmed defect: the25-pass loop added downstream units to an already accumulated
parent value on every pass. A parent feeding one2FU branch could grow to50FU
instead of2FU. The iteration cap concealed nonconvergence, not validated demand.

Replacement: validate unique named objects and existing/unique references, then
accumulate physical fixture-ID sets bottom-up over the directed supply forest.
Each fixture counts once per subtree. Missing references, duplicate names/edges,
multiple upstream supplies or cycles fail without sized outputs. Project total
units are the union of referenced fixtures, not max(segment units); probable
total flow uses the unchanged existing demand curve on that total. Unreferenced
fixtures are not silently assigned to a supply. No fixture-unit table, standards
or demand-curve coefficients changed; those still require professional review.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/water-72.xml`:57 tests passed.
All six permutations of a2FU/3FU branching tree require main5FU, branches2/3FU,
total5FU. A fixture named at two levels stays2FU, not4FU. Missing references,
duplicate names and cycles fail. Existing numeric-domain, topology, invalid-input,
independent EPA pressure and engine contracts pass. No provider, production/
customer data, deployment or paid service used.

Remaining: upstream pressure-path accumulation in the separate sizing result,
signed elevation/static pressure, reference demand methods, real network solver,
full candidate result identity and independent PE/benchmark acceptance. Existing
saved outputs unchanged. Rollback is a code revert without schema migration,
but restores inflated demand and should not be used as compatibility behavior.
