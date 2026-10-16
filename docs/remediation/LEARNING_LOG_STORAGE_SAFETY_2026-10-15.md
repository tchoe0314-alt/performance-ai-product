# Optional learning-log storage safety

Parent `febe3bac`; SEC-05 / data-lifecycle follow-up. Collection remains contained.

## Reproduced defects

With synthetic consent/global enable, the writer followed a log symlink, kept
existing0644 permissions, accepted unattributable records and serialized NaN.
Unowned records cannot reliably participate in user export/deletion. The current
chat workflow does not supply consent, so it still fails closed; this repair
does not connect or enable collection, change environment settings or read real logs.

## Implementation

Require a nonblank string owner ID in addition to the existing separate server
consent object; this is attribution, not account verification. Serialize finite
JSON before creating storage. Open with no-follow/nonblocking append flags,
require a regular file, set0600 through the opened descriptor, and hold a POSIX
advisory exclusive lock through write/flush. New logs are created0600.
Optional-learning failures remain contained from the main user workflow.

Existing positive consent fixtures now include synthetic owner IDs. Missing/
denied consent tests remain unchanged. No access control or numerical test was
weakened. Production feature activation is not implied.

## Isolated evidence

Disposable source/files/SQLite under `/tmp/civora-repair-verification.NBAOtD`;
guard denies outside writes/network/subprocesses. No customer data or paid calls.

- `results/learning-139.xml`:8 failed, original privacy/storage failures preserved.
- `results/learning-140.xml`:53 passed/40 subtests before concurrency case.
- `results/learning-141.xml`: **54 passed / 40 subtests**,0.93s. Owner/mode/symlink/
  finite JSON, consent/default-off, core security repairs and data lifecycle/backup
  tests. Eight concurrent writers append32 complete UTF-8 records without loss.
- `git diff --check`:PASS. No production privacy certification or full-suite claim.

## Limits / next required work

Advisory append locking does not yet coordinate deletion/redaction's atomic file
replacement; file-redaction rollback races remain open. Consent snapshots can
become stale, organization policies/retention/minimization are not complete, and
prior unowned records need operator-governed treatment. No historical log was
modified here. Parent directory/configured path remains a trusted operator boundary;
this is not defense against a fully compromised same-user filesystem.

This implementation targets the existing POSIX backend deployment. Unsupported
platform primitives fail closed through the optional writer; portability needs
explicit qualification before advertising learning there. Do not enable optional
learning until lifecycle/consent/reviewer requirements pass.

Rollback:review/revert isolated code/test change, no schema migration. Retain all
evidence; never re-enable collection to demonstrate a passing test. Reverting
reopens local-file exposure/attribution risks. No release gate passed.

Progress:0/5 release gates approved (0%), not coding completion.
