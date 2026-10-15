# Detector response budgets and cleanup

Parent: `3b0604c8`. Resource/availability follow-up to detector redirects.

Roboflow and generic responses previously buffered/parsed unconstrained JSON.
Their requests now stream with5second connect/20second read timeouts. A common
reader accepts only2xx JSON objects, caps streamed response bytes at2MiB,
checks a20second monotonic read budget between chunks, rejects nonfinite JSON,
and closes responses in finally on success, redirect, parse error or size/time
failure. No redirect fallback or insecure retry is provided. Real requests
Responses always expose iter_content; the json-only branch is for offline test
doubles and is separately size/finite checked after serialization.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/provider-66.xml`:
54 tests passed, one existing httpx warning. New cases verify oversize rejection
before consuming the tail, invalid JSON/array/NaN rejection, valid chunked JSON,
redirect cleanup and synthetic-clock expiration. Existing provider positive and
negative gateway/auth/download/redirect tests pass. No real provider/token,
production/customer data, paid API, deployment or payments used.

Limits are initial operating policy, not measured provider capacity. Deadlines
are cooperative between bounded reads, not process-preemptive wall-clock limits.
Configured endpoint trust/pinning, nested JSON complexity, complete error
sanitization, tenant data-sharing controls and deployed AppSec remain open.
No engineering/security release gate passed. Rollback is an isolated commit
revert without schema/data migration, but reopens unbounded response handling.
