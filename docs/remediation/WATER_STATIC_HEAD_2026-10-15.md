# Signed water elevation pressure

Parent: `f8931e1d`. ENG-06/Q13–Q14 elevation sign correction.

Both sizing and pressure-graph paths previously clamped negative elevation gains
to zero, losing modeled downhill pressure recovery. They now subtract the signed
elevation change multiplied by the unchanged caller-specified static coefficient.
Positive rise still loses pressure; negative rise gains pressure. No pump, datum
correction, flow split, pipe friction or pressure coefficient is invented.

Reference inspected2026-10-15: EPA EPANET2.2 manual describes total hydraulic
head as elevation plus pressure head:
https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10113EM.TXT
This supports sign/energy bookkeeping, not calibration or professional acceptance.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/water-76.xml`:70 tests passed.
Zero-flow oracles isolate elevation:60psi plus10ft rise gives55.67psi;10ft fall
gives64.33psi; equal rise/fall restores60psi. Both sizing and graph paths agree.
Existing fixture pressure, path/demand/topology/domain, EPA friction-unit,
hydraulic and engine-contract tests pass. No provider, production/customer data,
paid service or deployment used; existing saved outputs remain unchanged.

Open: datum-compatible elevations, real pressure bounds/cavitation/air effects,
outlet/minor losses, full network solver, final method identity/invalidation and
independent PE/reference-software qualification. Rollback restores the sign
defect; preserve old output history rather than recertifying it after a revert.
