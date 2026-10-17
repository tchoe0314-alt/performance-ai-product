# Session activity/read interleavings

Base revision: `71e21377dc0c750c569ffc8fffaabc3d44fe03ed`.
Addresses session-security/reliability follow-up to SEC-04; does not close its
entire browser, deployment or independent security-review scope.

## Confirmed defects and repair

`AuthStore.authenticate_token` captured a timestamp before selecting the session.
A second request could update `last_used_at` while the first SELECT waited,
causing the valid token to fail the strict future-timestamp predicate. Separately,
a delayed activity UPDATE could overwrite a more recent timestamp, shortening
the effective idle lifetime.

Two deterministic interleavings reproduce these defects without sleeps or
external services. Original source: **2 failed / 5 passed**. Original failure
report and log are retained in `session-concurrency-2026-10-17/`.

The repair reads the session snapshot before reading the validation clock, keeps
strict future and exact expiry boundaries, and uses a portable SQL CASE to avoid
moving activity backwards. Session-only columns are removed from the public user
record. Token hashing, absolute/idle lifetimes, revocation and rotation contracts
are unchanged. No migration or configuration change is required.

Additional regressions reject a future activity timestamp, reject a token that
expires while its read waits, and verify the returned user fields are unchanged.

## Verification

Disposable tracked-source copy under `/tmp/civora-session-verification.pW76oM`.
Existing `.venv311` packages only; no installation. OS sandbox denied networking
and writes outside the disposable root. Python audit hook also denied subprocesses
and reading existing external .env/database files. API tests used in-process ASGI
and temporary storage. No production/customer data, real email, paid services,
deployment or environment-file modifications.

- `expanded.xml`: **31 passed**, 1.34s. Session security, AuthStore, application
  authentication/health/session workflows and identity proof tests.
- `api.xml`: **2 passed**, 1.03s. Session rotation/revocation and identity API flows.
  One existing Starlette/httpx deprecation warning; dependencies not changed.
- Source/test diff whitespace check: passed. The final staged check reported
  trailing whitespace in the preserved pytest traceback blank lines in
  `before.log` and `before.xml`. Those historical output bytes were deliberately
  not stripped. This warning is not a test failure or a clean all-files check.

Preserved original report hashes:

|Report|SHA256|
|---|---|
|before.xml|`7e7664e886bd4a73ed43e5d3944a9c63f652a1bb2ac98575689440b18f471ca8`|
|expanded.xml|`128f2a5d40afd275371cfc1c9c3284d4e923e48e4a567af42fe48fe19e89060e`|
|api.xml|`a76bcfaf4476de4af8db4046ed7f9f2ffb038b4e23ce5c20699459e39ce68cf3`|

Committed copies normalize the final newline through the patch writer; original
reports remain temporary. Committed XML SHA256 values are:

- before.xml: `e45b60106ed35a7e4846a0f29946a72b2d58117690b6a107f990659185bc450d`
- expanded.xml: `8ff5556656315f0bf541f7f61152e1bd142073ed54f86871b1fecbdebdfbfc86`
- api.xml: `8c2cfc227a6558da7fbf5be13eee3d7febdbdc2679bfd0d23f29d20996b48dc8`

## Browser evidence and remaining limitations

The inherited, untracked candidate-review browser test is preserved, not certified
or included in this repair. Previous browser runs showed an intermittent session
expiration after a valid login; this repair fixes independently reproduced races,
but the causal link to that particular browser failure remains a hypothesis until
a new real-browser run confirms it. No prior browser success is claimed here.

The previous `/tmp/civora-repair-verification.NBAOtD` runtime and reports were no
longer present on resumption October 17. Existing committed summaries/hashes are
retained; missing raw temporary evidence is not silently recreated or certified.
Future candidate evidence should be durably preserved before environment changes.

PostgreSQL interleavings, rotation competing with activity updates, multi-host
clock behavior, full browser restore/conflict/reload, and independent security
review remain open. This change does not claim to solve every session race or
provide linearizable logout against already in-flight requests.

Rollback: revert only the repair/test group in a new commit; no database rollback
is needed. That reintroduces both demonstrated defects and must not be treated as
a safe release. Preserve these reports and the untracked browser work.

Progress: original reconstructed audit checks last verified **24/24 (100%)**;
not rerun here. Release gates **0/5 (0%)** approved. The full remediation goal,
seven broader engineering acceptance failures and external-review requirements
remain open; no defensible overall completion percentage is available.
