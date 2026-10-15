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

## Completed batch

backend-rz-56: `tests/test_[r-z]*.py`,327 tests+76 subtests passed in13.12seconds,
39 existing dependency deprecation warnings. XML SHA256:
`5389f2642ef8d1fe4480a163f5bff6129935fa14d9c8f4d1c2056029d5a5b03f`.
This is an alphabetical partition, not a representative reliability percentage.
The remaining alphabetical modules and remediation suite still need completed
current-candidate reports. backend-mq-57 was started separately; its completion
must be inspected, not inferred from this document.

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
