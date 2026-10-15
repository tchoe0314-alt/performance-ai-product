# Metadata callback isolation

Parent: `da48d1e9`. CAN-03 / SEC-10 follow-up. Not full remediation closure.

## Reproduced defect

`ProjectStore.update_project_metadata` passed its commit record directly to the
callback. A local callback could mutate valid canonical geometry, then return only
metadata; the method persisted that geometry without a design revision write.
This is an internal contract defect, not a demonstrated remotely supplied callback.

The new regression changes a placement through the normal canvas adapter and
clears the callback's calculation snapshot. Expected behavior independently requires
unchanged persisted and returned design/result fields, with the intended metadata
note updated. Before the repair that assertion failed on changed project input.

## Repair

Pass a deep copy to the callback and detach its returned metadata. Only returned
metadata enters the locked original record. Existing authorization, generation
protection, workflow merging, canonical export history and transaction remain.
No schema migration or numerical assumption changes.

## Evidence

Guarded disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`;
network and subprocesses denied. No production/customer data, paid APIs or deploys.

- `results/metadata-isolation-95.xml`: initial test failed because its deliberately
  broken object reference was rejected; not proof of persisted corruption.
- `results/metadata-isolation-96.xml`: valid geometry mutation reproduced the defect,
  1 failed assertion. Both reports retained.
- `results/metadata-isolation-97.xml`: **146 passed**, 21 dependency deprecation
  warnings, 6.63 seconds. Includes the new regression, atomic/concurrent exports,
  revision conflicts, project/artifact workflows, history and canonical gateway.
- `git diff --check`: pass.

## Limitations and recovery

The copy adds temporary memory proportional to the loaded project. Large payload
budgets and narrower callback projections remain required; do not remove isolation
to optimize memory. Callbacks must remain local/pure and must not perform database
or external work while locked. Arbitrary metadata ownership policy, PostgreSQL
qualification and broader all-writer audit remain open. No release gate passed.

Rollback: review/revert this isolated commit; no data migration. Reverting reopens
the callback mutation path. Historical damaged records are not automatically repaired.
