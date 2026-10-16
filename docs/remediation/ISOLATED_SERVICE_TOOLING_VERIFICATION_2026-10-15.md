# Previously isolation-blocked service/tooling checks

Candidate `d0894243758a69cd36c97f83c8c8e17e88d4fce4`.
No application/configuration changes, production/customer access, hosted requests,
deployment, paid API, package install or original evidence modification.

## Reviewed execution scope

Read all nine affected test modules and relevant startup/cleanup/runner boundaries.
Two deliberately narrow lanes replace neither the original full report nor its
guards. Both use the disposable source/SQLite tree and new output paths under
`/tmp/civora-repair-verification.NBAOtD`.

1. Service lane:real disposable Gunicorn/Uvicorn process on newly test-reserved
   loopback ports, fake-command startup argv fixtures, temporary worker-health
   server. Python guard admits only newly owned127.0.0.1 ports and propagates
   those ports to children. OS sandbox denies non-loopback networking and all
   writes outside the owned verification root (except/dev/null).
2. Tooling lane:OS sandbox denies ALL networking and outside-root writes. Reviewed
   subprocesses run dataset export, synthetic process-isolated benchmark helpers,
   fixture-only Git repositories, cleanup-rejection cases and local image triage.
   Hosted-gauntlet tests replace npx with a fake runner; no browser/hosted request
   is made. Git system/global configuration is disabled for fixture repositories.

The Python subprocess exception is enabled only inside these OS sandboxes. It was
not enabled for an unreviewed full suite. Original guard failure reports remain.

## Results and hashes

Reports in `/tmp/civora-repair-verification.NBAOtD/results/`:

|Report|Result|SHA256|
|---|---|---|
|service-159.xml|**28 passed**,13.73s|`8ee824a6f7af25939bfaafab04caa82f3581880921a008e38314212a9f6b5b41`|
|tooling-160.xml|**22 passed /7 subtests**,18 deprecation warnings,2.10s|`34e434a177aa40d6e2d1574cf31df642108cf7f29f8449ff427e43b397c3d263`|

Selections do not overlap:50 test functions/cases plus7 passing subtests. Exact
XML(classname,name) comparison matched **all41 previously blocked parent cases**
to passing results, with zero unmatched. Their47 failed outcomes in backend157
included multiple subtest failures; do not confuse47 outcomes with47 functions.

Covered prior blocked modules:backend keepalive, backend startup, worker health,
vision ground-truth dataset CLI, golden-load harness, hosted-gauntlet harness,
phase0 inventory, cleanup guards and vision-review-assist CLI. No test was skipped
or expectation weakened to obtain these passes. Real test servers terminated;
no leftover Gunicorn application process found. Original working tree remained clean.

## What this does and does not prove

Previously blocked checks are now verified for the stated local scope. Startup
PostgreSQL role tests use fake executables:they do NOT connect to PostgreSQL or
prove external-worker health in deployment. Fake golden-load plans test timing/
timeout/report mechanics, not engineering correctness or production capacity.
Synthetic review imagery and source-rights flags are not real-provider quality
or licensing acceptance. Hosted-gauntlet harness success is not hosted acceptance.

The original full backend run remains2,209 passed/56 failed. New scoped evidence
verifies its47 guard-blocked outcomes; separate158 verifies two obsolete revision
fixtures after repair. The **7 actual engineering failures remain open** (five
water readiness and two storm-deliverable cases). No fresh all-green full suite,
browser, independent engineering or deployed release acceptance is claimed.

## Next required work / progress

Proceed with the seven engineering failures and qualified hydraulic reference
inputs, then browser interactions, PostgreSQL races, recovery/load and independent
review. Freeze/rerun exact candidate evidence before any release decision.

- Reconstructed original audit checks:24/24 passed (**100%**), from broad155.
- Prior isolation-blocked parent cases:41/41 verified (**100%**) in these lanes.
- Release approval:0/5 gates (**0%**), not overall code completion.

Only this evidence record/ledger is committed in this batch. Rollback requires no
application change; preserve these and original failed reports as historical evidence.
