# Civora Hosted Canary

The hosted canary is a low-impact production monitor. It checks availability and release truth without creating projects, editing customer data, generating designs, or exporting artifacts.

## Automatic Public Checks

`.github/workflows/hosted-canary.yml` runs hourly, on pushes to `main`, and on demand. It verifies:

- the Civora website responds with the application shell;
- `/api/health` is successful and matches the expected Git revision;
- hosted product mode remains `private_alpha`;
- PostgreSQL and the database pool report healthy state;
- support, bug-report, and recovery configuration are present;
- `/api/auth/status` is reachable without exposing account counts;
- debug runtime and production-environment routes reject anonymous access;
- CORS approves exactly `https://civoraai.com`;
- two consecutive samples are healthy before the workflow passes.

Each attempt records endpoint timings and blocker codes in a redacted artifact. Retries therefore do not erase intermittent failures.

## Optional Authenticated Checks

Create a dedicated, least-privilege canary account. Do not reuse a founder, administrator, employee, or customer account.

Add these GitHub Actions repository secrets:

- `CIVORA_CANARY_EMAIL`
- `CIVORA_CANARY_PASSWORD`

The credentials are passed through the process environment, are never accepted as command-line arguments, and are never written to the report. When configured, the canary also verifies:

- authenticated runtime reachability;
- PostgreSQL runtime state;
- queue monitoring, recent failures, and stale jobs;
- clean prior process shutdown;
- backup and restore evidence;
- configured escalation, monitoring, and rollback owner presence.

Use **Run workflow** with **Require configured authenticated canary credentials** enabled when authenticated proof is mandatory. The workflow fails if credentials are absent or runtime evidence is blocked.

## Local Operator Command

```bash
python3 backend/scripts/run_hosted_canary.py \
  --frontend-url https://civoraai.com \
  --api-base-url https://api.civoraai.com \
  --expected-revision "$(git rev-parse HEAD)" \
  --expected-product-mode private_alpha \
  --attempts 12 \
  --retry-delay-seconds 10 \
  --required-consecutive-successes 2
```

Set `CIVORA_CANARY_EMAIL` and `CIVORA_CANARY_PASSWORD` only in the invoking process when authenticated proof is needed.

## Response

- A revision mismatch usually means deployment is still rolling forward; confirm the provider deployment before retrying.
- Repeated `502`, timeout, or latency spikes require provider/runtime investigation even when a later retry passes.
- Queue failures or stale jobs require triage before relying on background results.
- A CORS or anonymous-debug failure is a security/release blocker.
- Canary success is not public-launch approval, professional review, billing approval, or construction readiness.
