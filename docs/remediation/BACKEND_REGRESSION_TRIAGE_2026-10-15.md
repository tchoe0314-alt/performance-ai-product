# Broad backend regression triage — not final release acceptance

## Frozen intermediate run

`full-backend-04` executed against the disposable source copy prepared after
`e3482dc4`, before the invitation-proof implementation. It recorded2,312 passed,
56 failed assertions and264 passed subtests in437.86seconds. JUnit includes
subtest records, so its suite total2,632 is not the pytest method count.

The guard disabled network, subprocesses, outside writes and existing database
access. No failures were hidden or removed to obtain a green full-suite claim.

|Failure category|Failed assertions|Disposition|
|---|---:|---|
|Isolation restrictions|47|41 distinct test identities; includes repeated unittest subcase failures. New safe harness verification below|
|Missing copied tracked sample fixture|1|Snapshot excluded root data. Exact tracked sample is present in the later tracked-file copy; engine-contract suite passes without invented data|
|Contract/assertion failures|8|One real drawing-only export regression plus current-method/legacy fixture mismatches. All corresponding targeted suites now pass as described below|

Original report SHA-256:
`2bfae477cbb9f042c734993ea15d39e4ba81e579985a24534e4bbac8d78991d2`.
Location: `/tmp/civora-repair-verification.NBAOtD/results/full-backend-04.xml`.

## Fresh targeted follow-up

- `cli-24`:45 tests and7 subtests PASS under macOS sandbox-exec.37 previously
  blocked test identities now match passing cases; four local-server tests
  remain unmatched. A separate sandbox probe proved owned output allowed,
  outside-owned-area write denied and network bind denied. Subprocesses ran
  only inside that OS sandbox; no production access or network was enabled.
- `broad-failures-23`:48 PASS across calculation export versions, current drawing,
  alternatives, direct persistence, deterministic scenario evidence and resume
  echoes. The full run's direct persistence failure was already repaired and
  verified with the invitation regression set, not counted as a new engine bug.
- `export-integration-25`:64 PASS across engine contracts, real drawing exports,
  result freshness, calculation history, atomic exports and LandXML.

Reports have these SHA-256 anchors:

|Report|SHA-256|
|---|---|
|cli-24.xml|`1c638cea46e792f70ff23bcc17e8e2a2fdafd93b6a3b4d593896fd4706f66392`|
|broad-failures-23.xml|`e45853508a54c9927da2d4c881f7b3e223211279f2215cfb642e9b7c0239e746`|
|export-integration-25.xml|`d2915ba03a9f6aa0315903498f2ff4070ebe884c4cb7c07fb337d9b17b8e1f65`|

These reports are temporary local artifacts; hashes are not third-party
attestation. Do not add overlapping suite totals into a fabricated unique count.

## Actual export repair

The new calculation-version gate inadvertently blocked drawing-only exports.
That path now reconstructs the authorized saved drawing and compares every
field except publication timestamp. It republishes with the server's current
timestamp and rejects stale/tampered geometry or injected engineering facets.
It never grants a calculation identity to a drawing. Drawing history uses input
freshness without a nonexistent calculation revision; calculated export gates
continue requiring method identity. Real PDF/DXF history-preservation tests and
a smuggled-calculation negative test pass.

Current-method positive fixtures now identify simulated execution explicitly.
Old unbound calculated exports remain negative tests requiring recalculation.
Resume tests use a current-method checkpoint for the positive echo-size case;
separate negative coverage prevents legacy checkpoints being recertified.
No expected numerical result or original audit evidence was changed here.

## Remaining acceptance

At this report's initial commit, four owned-local-server tests, final full regression on the latest frozen
candidate, complete browser acceptance, PostgreSQL concurrency and external
engineering/security validation remain unverified. Do not call this a clean
full backend run or a closed audit. Rollback of the drawing fix must preserve
both saved-snapshot integrity and calculated-export version gates.

### Subsequent owned-server verification

`owned-network-27` passed5 tests in11.66seconds: both keepalive cases, both
worker-health server cases and a polling configuration case. All four previously
unmatched server-test identities now pass. The OS policy denied non-loopback
network access and outside-owned-area writes; the Python guard admitted only
ports allocated by the reviewed tests and propagated those allocations to their
disposable child servers. Synthetic storage/providers-none settings remained in
force. Test cleanup shut down its servers. No existing local or hosted service
was used. An initial invalid sandbox-profile syntax attempt is preserved
separately in `owned-network-26.log`, not labeled a product failure.

Report: `/tmp/civora-repair-verification.NBAOtD/results/owned-network-27.xml`.
This closes the isolated-harness restrictions for the matched cases, not final
full-suite acceptance of the latest source revision.

Only generated caches and duplicate environment files inside the disposable
verification directory were removed for disk space. No original workspace,
source data, audit evidence, installed runtime or user cache was removed.
