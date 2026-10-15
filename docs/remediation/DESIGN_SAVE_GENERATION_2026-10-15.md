# Design save generation prevents content-token ABA

Parent: `ec62c93a`. CAN-03 stale-write detection.

Reproduced before repair: renameA→B→A through both full/shell saves recreated
the original content-only revision token. An older save could become valid again.
aba-86 preserves both failed regressions (2 failures;12 deselected).

Full/shell design saves now increment a server-owned design_save_generation_v1
under their existing transaction locks. Revision hashing includes it when present.
Legacy records without it retain their existing hash until normal save adoption;
no migration/record rewrite performed. New creation starts1, ignoring incoming
counter claims. Replacements/history preserve prior snapshots; no history erased.
Calculation/archive publication does not increment this design counter.

An intermediate aba-87 run found metadata-only replacement dropped the counter
(133 passes/1 failure). The metadata patch boundary now preserves the current
counter and rejects attempts to introduce/reset it through callback output.
Original failed reports remain preserved; no assertion weakened.

Final isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/aba-88.xml`:135 tests passed,
3.55seconds. Scope: new full/shell change-and-restore rejection and metadata
counter drop/forge cases; existing revision races, recovery, store fast paths,
project/job workflows, calculation history, browser ownership and import trust.
No provider, production/customer data, deployment, paid services or schema change.

Open: all low-level revision enforcement, candidate/metadata-only operation
generations, PostgreSQL execution, legacy adoption and browser qualification.
This closes ordinary full/shell save ABA, not every distributed update sequence.
Rollback must not erase counters or reuse old tokens; prefer roll-forward or
explicit conflict/reopen compatibility rather than silently reviving stale saves.
