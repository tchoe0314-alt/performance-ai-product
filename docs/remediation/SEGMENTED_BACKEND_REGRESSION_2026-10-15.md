# Segmented current-candidate backend regression

Application source: `443451ee16559d8f10273f16a130da957ed2cbc1`.
No application edits during these runs. Reports remain under
`/tmp/civora-repair-verification.NBAOtD/results/`.

## Interrupted attempt

backend-55 ran tests excluding tests/remediation in the guarded disposable copy.
Its process/session subsequently disappeared; the final XML was not written.
The partial log reached55% with no printed failures, but cannot establish a
completed count or pass. Cause of termination is unknown. The log is preserved.
Do not restart solely on observation timeout; process absence and missing session
were directly checked before starting separately reported batches.

## Completed batches

backend-rz-56: `tests/test_[r-z]*.py`,327 tests+76 subtests passed in13.12seconds,
39 existing dependency deprecation warnings. XML SHA256:
`5389f2642ef8d1fe4480a163f5bff6129935fa14d9c8f4d1c2056029d5a5b03f`.
This is an alphabetical partition, not a representative reliability percentage.
backend-mq-57: `tests/test_[m-q]*.py`,397 tests+25 subtests passed in132.28seconds,
24 existing dependency deprecation warnings. XML SHA256:
`f3bc9fa96f6a30b75b65ff8cb3fd0528bf50cd3ebdff8beb1a59fcf70b00156f`.
The process returned exit0. A one-second diagnostic sample during execution
recorded201.3MB physical footprint/278.9MB observed peak; this is not a workload
capacity or memory-leak qualification. Sample retained alongside the report.

backend-ab-58: `tests/test_[a-b]*.py`,501 tests+10 subtests passed in31.46seconds,
24 existing dependency deprecation warnings; process exit0.

backend-cf-59: `tests/test_[c-f]*.py`,811 tests+42 subtests passed in177.52seconds,
33 existing dependency deprecation warnings; process exit0. XML SHA256:
`cc5c435c01b2ebc6ace8df5bae3eaf6192eb5e5176f373a3d87064860c3b4e1d`.

These four completed alphabetical selections do not overlap:2036 tests and153
subtests passed. Remaining G–L modules and remediation tests still need completed
current-candidate reports. backend-gl-60 has been started separately and is not
certified by this document. No full-backend or release pass is claimed.

### G–L completion and policy-test reconciliation

backend-gl-60 completed exit1:205 tests+42 subtests passed, one test failed,
22 warnings,101.74seconds. XML SHA256:
`fc74699554f5bea2d3f231edea54b409e116af04c67f6878d1b6f422fe512fa7`.
The failure was test_explicit_open_registration_and_legacy_local_defaults,
expecting private_alpha signup open by default. The implemented invitation-only
contract (fa5f9c52) and actual API regressions require it closed. Reopening the
application to satisfy this assertion would restore the enrollment weakness.

That outdated assertion was replaced with explicit default and operator-policy
matrices covering all four modes. This is a documented security contract test
correction, not a changed numerical oracle or suppressed failure. Original GL
failure XML/log remain unchanged. Application source remains443451ee; only this
test and execution documentation changed.

policy-61:57 tests passed, one existing httpx warning,1.43seconds: updated policy
matrix, enrollment/recovery API and release safety. No real mail/providers or
production/customer data used. This targeted rerun does not replace the failed
GL report or constitute a new all-green full suite. Remediation-only current
qualification and final unified candidate acceptance remain outstanding.

### Current remediation and evidence harness qualification

Source revision e88f68e7 (same application code443451ee, updated enrollment
policy regression). remediation-62 ran tests/remediation excluding only
test_p01_evidence.py:179 tests+77 subtests passed in3.32seconds, one existing
httpx deprecation warning. Includes original reconstructed24 assertions, core
repairs, compatibility and newer numerical/security/persistence/terrain cases.
XML SHA256: `efa1f023a5be66b487ff99324ae0a1e7057169aee842adb4d804f7a6798700e2`.

harness-63 separately ran test_p01_evidence.py:18 tests+4 subtests passed in
0.09seconds. Its writes/tamper cases are disposable fake bundles, not edits to
original evidence. These two selections do not overlap. No original audit
expectation or recorded failure was erased. No network, production/customer data,
paid service or deployment used. Python guards denied subprocess and outside
writes throughout these two checks.

All top-level alphabetical backend partitions have now completed at the same
application source, with one documented obsolete policy-test failure followed
by its stronger57-test contract rerun. This is not a single all-green run on a
final frozen release. Browser, PostgreSQL, performance/recovery, independent
engineering/security review and unfinished implementation remain required.

## Isolation / cleanup

Existing disposable Python runtime and tracked-source copy; env-i with explicit
synthetic storage, blank DATABASE_URL, providers disabled, no bytecode/cache;
macOS sandbox denied external network and writes outside the owned root.
Python guard allowed only newly test-owned loopback ports and propagated them
to approved disposable child processes. Existing localhost services were not
authorized. No production/customer data, paid API, deployment or payment used.

Only the stopped disposable Next server's generated .next-identity-check cache
was removed for space after validating its path/non-symlink and no listener.
Original repository/user caches, databases and test reports were not removed.
The removed generated cache is rebuildable; no unique source/evidence lost.

No release gate passed. Full browser/PG/engineering/security/operational
acceptance remains open; earlier artifacts cannot certify newer application code.
