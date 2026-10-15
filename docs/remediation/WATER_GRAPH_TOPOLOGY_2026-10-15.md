# Water pressure topology qualification

Parent: `4737c26c`. ENG-06/Q14 supported-solver boundary.

Confirmed: graph traversal accepted multiple incoming supply paths and selected
the maximum resulting node pressure without solving network flow equilibrium.
Cycles/duplicate edges could appear solved depending on traversal order. The
simplified engine now requires a source-reachable directed supply tree: typed
node IDs, one parent per non-source node, no edge into the source/self-loop,
and no unreachable/disconnected cycle. Unsupported topology fails before any
pressure output. This prevents false solver-success claims, not implements the
general network solver still required for broader water-network functionality.
Fire-flow output carries pressure-graph warnings and no longer documents loops
as conservatively supported. Supported tree pressure arithmetic is unchanged.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/water-70.xml`:46 tests passed.
Six unsupported topology cases require failure/empty pressures; all six input
permutations of a branching tree require the same independently specified
pressures with two successive5.587psi losses. Input validation, independent EPA
unit checks, hydraulic/fire-flow regressions and engine contracts also pass.
No real provider, production/customer data, paid API or deployment used.

Open: true looped/multi-source equilibrium solver and reference-software/PE
qualification, hydraulic demand continuity, signed elevation-pressure behavior,
extreme numeric bounds and other engineering families. Existing saved outputs
are not changed. Exact final release identity/version acceptance remains needed.
Rollback is an isolated code revert without schema migration but restores false
topology success. Do not advertise looped-network support to avoid this guard.
