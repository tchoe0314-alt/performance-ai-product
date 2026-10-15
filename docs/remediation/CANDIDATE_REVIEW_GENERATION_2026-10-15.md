# Candidate review consumes its revision

Parent `450ca4f3`. CAN-03 / SEC-10 extension of the existing design-generation rule.

## Evidence and repair

The locked candidate-review writer checked a content hash but did not advance
the design save generation. Repeating an identical review snapshot left the same
token reusable. Content restoration (A/B/A) could likewise permit an old request.

A regression applies identical valid review state twice and requires distinct
tokens. It then replays the first token with different decisions, requiring a
conflict and exact preservation of the complete saved record. This failed before
the repair. The writer now increments the existing server-owned generation under
its row lock and atomically saves metadata alongside review inputs. The returned
shell contains the committed generation. It does not rewrite the calculation.

No numerical convention, schema or external service changed. Existing reviewed
states remain compatible; old tokens correctly conflict after a new review write.

## Isolated verification

Disposable source/SQLite and write/network/subprocess guard under
`/tmp/civora-repair-verification.NBAOtD`; no production/customer data or paid calls.

- `results/candidate-generation-98.xml`: 1 failed, reproducing token reuse.
- `results/candidate-generation-99.xml`: 91 passed / 6 failed, implementation
  missing its local helper import; retained as development failure evidence.
- `results/candidate-generation-100.xml`: **97 passed**, 21 dependency deprecation
  warnings, 6.21 seconds. Covers revision conflicts, candidate simultaneous/stale
  writes, fast paths, project workflows, atomic exports and canonical gateway.

Not a full current suite, PostgreSQL test or browser acceptance. Client inbox
source tokens, full metadata policy and remaining writer inventory stay open.
No release gate passed. Rollback requires review/revert of this isolated change;
no data migration, but reverting reopens token reuse for candidate review writes.
