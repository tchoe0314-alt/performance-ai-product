# Live consent/account authority at optional collection boundary

Parent `b2458c85`; SEC-05 data-lifecycle follow-up. Not feature activation.

## Reproduced defect

A synthetic account opted in, captured its consent dictionary, then withdrew.
Passing the old dictionary still persisted a learning event. A dictionary proves
only an earlier observation, not current account existence/permission.

## Repair

All three optional append APIs require a server-owned callable in addition to
the initial opt-in snapshot. After acquiring the stable log lock, they query the
owner's current account/consent authority and require matching user ID, active
account and explicit opt-in. Missing, mismatched, denied or failed lookup rejects
without opening the data file. Global collection policy is rechecked under lock.

`database_learning_consent(db)` joins users to memory consent; absent users and
missing consent fail closed. Public consent updates share the log -> database
ordering while collection is globally enabled, so acknowledged withdrawal cannot
overtake an already-authorized file write. Deletion already holds the same lock
through database commit. Existing chat callers remain disconnected/no consent
provider: no collection was enabled or production configuration changed.

Filesystem-only positive fixtures inject explicitly synthetic live authorities;
real database cases independently verify active, withdrawn and deleted accounts.
Old snapshot-only positive fixtures now require the stronger contract; denial
and default-off assertions remain. No numerical behavior changed.

## Evidence

Guarded disposable source/SQLite/files under `/tmp/civora-repair-verification.NBAOtD`;
no production/customer data, paid API calls, deployment or external services.

- `results/live-consent-146.xml`:1 failed, stale consent reproduced before repair.
- `results/live-consent-147.log`/XML:collection error from new test import ordering;
  preserved, not product acceptance. Fixed test import, not an expected outcome.
- `results/live-consent-148.xml`:68 passed/40 subtests before waiting-writer case.
- `results/live-consent-149.xml`: **69 passed / 40 subtests**,1 dependency warning,
  2.78s. Includes actual live database authority, callback failure/owner mismatch,
  locked waiting writer, append/deletion rollback races, log safety, lifecycle,
  backups, memory/collaboration and core repairs. Reports overlap; do not sum them.
- `git diff --check`:PASS. No full browser/PostgreSQL/multi-host acceptance claim.

## Remaining requirements / recovery

Trusted operator/in-process code must bind the lookup to the same database/account
authority and log path used by deletion/withdrawal; client-supplied callbacks are
not an API feature. Organization consent policy, retention/minimization, data
sharing agreements, redaction, historical unowned records and independent privacy
review remain required before optional learning is enabled. Global configuration
changes, alternate writers and distributed filesystem lock behavior need separate
operational qualification. Locks are POSIX and currently have no wait budget.

Collection failures remain contained rather than breaking engineering requests;
operational diagnostics/explicit eligibility UX are separate requirements.
Rollback:review/revert isolated change, no schema migration. Preserve evidence;
reverting reopens stale/deleted-account consent acceptance. Do not enable collection
or weaken consent checks merely to demonstrate functionality.

Progress:0/5 release gates approved (0%), not coding completion.
