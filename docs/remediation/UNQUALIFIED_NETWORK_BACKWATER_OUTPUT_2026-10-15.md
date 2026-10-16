# Do not publish unqualified network backwater numbers

Parent `0d2045e7`; ENG-06/AI-01 evidence integrity follow-up. Partial safeguard,
not a completed branched-network solver or release approval.

## Current failure diagnosis

The unchanged manual storm-export acceptance fixture is blocked by
`storm_backwater_or_surcharge_invalid`. Diagnostic161 confirms its branched
stationing is unqualified. The previous code nevertheless emitted adjusted HGL,
terminal HGL and surcharge amounts from cumulative serialized stationing.
Those numerical outputs can change when unrelated branches are reordered.
This is not reliable evidence that the actual design is physically surcharged.

The new independent regression requires two permutations of the same branched
network to produce the same explicit method blocker and NO computed adjusted
backwater profile, terminal HGL or surcharge amount. It failed before repair.

## Implementation

The existing linear influence calculation now runs only on a verified connected
chain. Other topologies retain source/per-pipe hydraulic evidence, marked
review-required with serialized-preview stationing unverified. Their backwater
result is false with `qualified_network_backwater_method` missing and no numerical
adjusted profile/surcharge claim. Export remains blocked; no test expected-ready
result or engineering tolerance was weakened.

This is not substituting a narrower product for the intended network capability:
full branched-network hydraulics, boundary conditions, junction handling and
independent reference acceptance remain mandatory open work. The chain influence
approximation also still requires review; ordering it correctly did not validate
its hydraulics. Root cached HGL/EGL view ownership/refresh needs separate checking.

## Isolated evidence

Disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`, guarded
against outside writes/network/subprocesses. No production/customer data, paid
API, deployment or independent-review claim.

- `results/storm-export-diagnostic-161.log`:retained source of export blocker.
- `results/backwater-162.xml`:1 failed, unsupported numerical output reproduced.
- `results/backwater-163.xml`:50 passed,21 deprecation warnings,2.18s; new regression,
  chain/tailwater/producer and result/export-version coverage.
- `results/backwater-acceptance-164.xml`: **16 passed /4 failed**,21 warnings,12.72s.
  Unchanged looped-water pressure/fire-flow cases, manual storm export and controlled
  benchmark readiness still fail. Other3 of the prior7 engineering failures were
  not rerun in this selection; none are claimed closed.
- `results/remediation-165.xml`: **444 passed /81 subtests**,22 warnings,6.98s.
  All remediation tests including original24, evidence harness and new safeguards.
- Selections overlap; do not add totals. `git diff --check`:PASS.

Buildv14 keeps older results historical/unverified until actual execution. No
stored output deleted, no schema migration or import recertification.

## Recovery / remaining work

Qualified reviewer reference network is still requested; the application must not
fabricate boundary/junction inputs to satisfy old success fixtures. Continue the
full intended network implementation/validation and other independent remediation.
Review/revert this isolated change if necessary, keeping build identifiers distinct;
reverting reopens misleading adjusted-profile output. Preserve all failures.

Progress:original reconstructed audit24/24 (**100%**); release0/5 (**0%**).
Neither is a defensible overall coding-completion percentage. Full goal remains open.
