# Water input validation

Parent: `99cd0ea3`. ENG-06/Q13–Q14 invalid-input qualification.

Confirmed: sizing accepted nonfinite/domain-invalid pressure/fixture/segment
inputs; pressure graphs defaulted missing dimensions and used falsy fallbacks
that could replace explicit zero flow with a nonzero alias. A shared finite
numeric validator now rejects booleans/nonfinite/negative physical magnitudes,
requires positive sizes/roughness/velocity/loss targets and permits signed finite
elevation gains. Sizing reports structured failure before cloning/calculation.
Graph preflight validates the whole request and returns no solved segments,
no pressures and min_pressure=None on failure. Explicit zero flow is preserved.
The friction helper rejects invalid inputs rather than clamping them to zero.

Fresh isolated reports water-68 and final water-69 under
`/tmp/civora-repair-verification.NBAOtD/results/` each record39 tests passed;
they overlap and must not be summed. Scope: new invalid/zero/immutability cases,
independent EPA pressure-unit cases, existing water/hydraulic math and engine
contracts. No expected numerical oracle weakened, provider calls, production/
customer data, paid service or deployment used. No stored records changed.

Remaining: duplicate/missing object identities, topology/loops, path accumulation,
pressure gains from downhill elevations, physically extreme finite overflow,
fixture/design standards, typed unsupported objects and reference/PE acceptance.
This is not full water/fire-flow engineering qualification. The development
build remains unreleased; final candidate must bind these changes to exact Git
identity/configuration and requalify result-version behavior before deployment.
Rollback is an isolated commit revert, no schema migration; it reopens invalid
input success/defaulting and should not be used to accept incomplete engineering.
