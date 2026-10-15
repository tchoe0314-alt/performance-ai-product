# Water production integration: evidence and open solver mismatch

Parent: `760aaa7f`. ENG-06 production-depth projection.

Fresh complete production-depth run production-78 reported2 failures/16 passes,
21 dependency warnings in3.51seconds. Failures are the two existing positive
looped-water fixtures, which expect pressure/fire-flow readiness from the former
path traversal. The repaired tree solver rejects those loops. Original tests
and failed report remain unchanged. They are not waived or called resolved.
Loop-ready production claims need an actual network equilibrium solver with
explicit demand/boundary semantics and reference/PE acceptance. Inference of
nodal demands from conflicting assigned loop flows is not authorized engineering
truth. Merely changing these assertions would not supply the missing solver.

Separate confirmed report defect: source pressure used Python or-chaining, so
explicit0psi could select an unrelated72psi fallback. Selection now uses the
first non-missing finite value, preserving0. Failed/unsupported pressure graphs
now project min pressure/margin as None, not a fabricated computed0psi.

Fresh focused report production-79 (same isolated root/results) records17 tests
passed: zero-pressure precedence, unknown loop pressure projection, fire-flow
validation and existing hydraulic math. All reports live under
`/tmp/civora-repair-verification.NBAOtD/results/`. No provider, production/customer
data, paid API or deployment used. No stored designs/results changed.

The focused pass does not erase the2 production-suite failures. Remaining:
general looped-network implementation/contract, production readiness integration,
independent solver benchmark, final method identity and professional review.
Rollback of this report repair restores zero-as-missing and invented pressure
display; no schema migration required. Preserve the unresolved integration tests.
