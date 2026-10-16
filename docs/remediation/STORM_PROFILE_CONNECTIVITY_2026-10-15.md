# Storm chain profile connectivity

Parent `a5fc7c9c`. ENG-06 / CAN-02 follow-up; partial repair, not hydraulic qualification.

## Reproduced error

Backwater enrichment used the final row of a flattened serialized segment profile
as the outlet and used cumulative serialized stationing for its existing influence
calculation. Reversing the same two-pipe chain changed the reported backwater
validation. List order is not engineering connectivity.

`_ordered_storm_chain` follows explicit directed node relationships and validates
a single connected chain. Enrichment orders that chain before existing hydraulic
and profile computation. No new hydraulic formula or design tolerance was added.
Branches, merges, cycles, disconnections, self-loops and missing nodes cannot claim
continuous chain stationing; backwater validity requires qualified stationing and
these cases carry `qualified_network_backwater_method` as missing evidence.

This containment does NOT complete advertised branched-network functionality.
The existing linear influence approximation itself still needs independent
method/reference review. Network hydraulic equilibrium, junction controls,
multiple outlets and reliable backwater propagation remain required work, not
substituted by the narrower chain repair. Independent pipe HGL calculations do not
establish complete network accuracy. Existing manual hydraulic failures are not
waived. Reviewer reference network requested asynchronously; unrelated repairs
can continue without waiting.

## Evidence

Reports under `/tmp/civora-repair-verification.NBAOtD/results/` from guarded
disposable source/SQLite; no production/customer data, paid calls or deployment.

- `storm-order-133.xml`:1 failed, original order dependence preserved.
- `storm-order-134.xml`:17 passed/2 failed. The two failures are the previously
  recorded looped-water fire-flow/pressure acceptance cases; assertions unchanged.
- `storm-order-135.xml`: **38 passed**,21 dependency deprecation warnings,2.20s.
  Actual enrichment reversal regression, all six three-pipe orderings, unsupported
  topology cases, producer consistency and result/export-version tests.
- The selections overlap; do not sum their pass counts.
- `git diff --check`:PASS. No fresh full planner/browser/PostgreSQL qualification.

Buildv12 retainsv2-v11 as unverified historical results until actual execution.
No persisted model migration or automatic result repair.

## Risks / recovery

Some formerly "valid" branched/disconnected profiles now fail closed, exposing
missing modeling instead of manufacturing one long profile. This is a safety
restriction, not removal of the obligation to implement/qualify network hydraulics.
Do not restore list-order behavior or change test expectations merely for green
acceptance. Rollback requires review/revert; no schema migration. Keep build
identifiers distinct and prior results historical.

Progress:0/5 release gates approved (0%), not coding completion.
