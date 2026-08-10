# Civora RC1 Incident Runbook

This runbook covers controlled invite-only operations. It does not replace organization-specific security, privacy, legal, or engineering incident procedures.

## Intake

Users can submit an issue from **Help > Support**. The server stores the account, optional project, category, severity, summary, details, sanitized client context, status, and timestamps. Authentication secrets, cookies, and token-like context keys are removed.

Operators can inspect the persisted queue without exposing a public admin route:

```bash
PYTHONPATH=. python3 backend/scripts/triage_support_requests.py --status received
PYTHONPATH=. python3 backend/scripts/triage_support_requests.py --fail-on-urgent
PYTHONPATH=. python3 backend/scripts/triage_support_requests.py \
  --request-id support_example --set-status triaged
```

Run the urgent check from authenticated operational monitoring. A nonzero result means at least one unresolved P0/P1 request needs an owner.

Required configuration:

- `CIVORA_SUPPORT_CONTACT_URL` or `CIVORA_SUPPORT_EMAIL`
- `CIVORA_BUG_REPORT_URL`
- `CIVORA_ESCALATION_CONTACT`
- `CIVORA_MONITORING_OWNER`
- `CIVORA_ROLLBACK_OWNER`

The hourly hosted canary and its redacted evidence are documented in [hosted-canary.md](hosted-canary.md). Repeated transient failures still require investigation even if a later retry succeeds.

## Severity

| Severity | Examples | Immediate action |
| --- | --- | --- |
| P0 | Data exposure/loss, cross-account access, fabricated source trust, materially unsafe or misleading output | Pause affected workflow, preserve evidence, notify owners, roll back or disable |
| P1 | Primary workflow blocked, repeated save/reopen failure, wrong/stale output presented as current, hosted auth outage | Same-day triage, workaround or rollback, affected-user notice |
| P2 | Recoverable workflow defect, confusing state, moderate performance or accessibility issue | Assign and schedule; monitor for escalation |
| P3 | Cosmetic issue or low-impact enhancement | Backlog with evidence |

## First 15 Minutes

1. Record the request ID, project ID, user impact, deployment revision, time, browser/device, and source files involved.
2. Decide whether users must stop relying on affected output.
3. Preserve logs and artifacts. Do not delete or rewrite the affected project.
4. Check frontend health, backend `/api/health`, auth, queue/runtime monitoring, database connectivity, file storage, and provider status.
5. Name an incident owner and a communications owner.
6. For suspected privacy or cross-account access, stop affected access and follow counsel/security notification procedures.

## Diagnose

- Reproduce with a permission-cleared copy when possible.
- Compare the current deployment IDs with the last known-good release record.
- Check browser console/page errors and failed requests.
- Check backend request IDs, tracebacks, restarts, queue failures, stale jobs, rate limits, and timeouts.
- Check project save/load, storage paths, database rows, artifacts, and export freshness.
- Check source/provider provenance before treating a geometry or calculation issue as an engine defect.
- Confirm whether the issue is isolated to one project, one account, one provider, one browser, or the release globally.

## Contain and Recover

1. Pause new invites for P0/P1 incidents.
2. Disable only the affected capability when a narrow safe switch exists; otherwise roll back the frontend/backend deployment.
3. Do not restore a database over production without a named owner, backup identifier, verified restore procedure, and maintenance plan.
4. Re-run health, auth, project persistence, one engineering workflow, and one export workflow after recovery.
5. Confirm the exact corrected revision and deployment IDs.
6. Notify affected users with plain impact, scope, workaround, and status. Do not speculate.

## Data-Lifecycle Incidents

- Account export must not include password hashes, salts, bearer tokens, cookies, API keys, or another user's project data.
- Account deletion must revoke authentication, remove solely owned data and files, and stop when shared ownership cannot be resolved safely.
- If export or deletion behavior is uncertain, pause the request and escalate; do not report completion.
- If account deletion reports pending storage cleanup, use the dry-run-first quarantine cleanup command in `rc1-data-lifecycle-and-recovery.md`. Do not report completion until the matching quarantine directory is removed and a repeat dry run is clear.
- For restore events, compare database row counts and content hashes and verify referenced files separately.

## Closeout

Record:

- root cause;
- affected users/projects and time window;
- data or output impact;
- containment and recovery actions;
- exact revisions/deployments;
- tests and human checks run;
- user communication;
- permanent corrective action;
- monitoring or runbook change;
- owner and due date.

An incident is not closed until affected workflows are retested and any user-facing reliance risk is communicated.
