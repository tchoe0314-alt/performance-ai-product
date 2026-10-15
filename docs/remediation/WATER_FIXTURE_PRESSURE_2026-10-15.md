# Fixture pressure acceptance

Parent: `970de045`. ENG-06/Q13 previously unused required_pressure input.

Sizing previously returned success without checking fixture requirements.
It now reports pressure_requirements_met and per-fixture supply-endpoint checks,
including required pressure, calculated pressure, scope, reason and pass state.
Insufficient pressure/unconnected fixture/unmodeled branch length makes sizing
success=false with diagnostic results retained. No fixtures gives acceptance=None,
not a fabricated fixture pass. Existing successful complete requests still work.

Endpoint comparisons use unrounded pressure; display rounding cannot turn
14.9996psi into a passing15psi requirement. A separate raw calculation field is
stored on output segments while their existing rounded display field remains.
The minimum endpoint among a fixture's explicit references is conservative.
An extra fixture branch_length is not silently ignored or assigned an invented
diameter: it requires explicit pipe modeling before pressure qualification.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/water-75.xml`:66 tests passed.
New checks cover above/equal/below/below-but-rounds-equal thresholds, unconnected
fixture, unmodeled branch and no-fixture unknown acceptance. Existing pressure
path/demand/domain/topology/EPA-unit/hydraulic/engine-contract regressions pass.
No code/standard pressure threshold changed; caller-required pressure is used.
No provider, production/customer data, deployment, paid service or migrations.

Remaining: optional automatic fixture-branch modeling with explicit diameter/
material/elevation data, friction/minor losses to actual outlets, signed static
head, standards/fixture-table review, UI/report projection, final method identity
and independent PE/reference qualification. Modeled endpoint pass is not final
fixture design approval. Rollback is a code revert without data migration but
restores unchecked fixture requirements and must not recertify old results.
