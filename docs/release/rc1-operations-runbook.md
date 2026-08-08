# Civora RC1 Operations Runbook

This runbook separates automated technical evidence from actions that require an accountable operator, infrastructure approval, professional review, or counsel.

## User Support

- Workspace issue intake: `https://civoraai.com/support`
- Bug intake: `https://civoraai.com/support?category=bug`
- Signed-in reports are persisted through `POST /api/support/requests` and receive a reference ID.
- Diagnostic context is sanitized before storage. Users should still never submit passwords, tokens, private keys, or credentials.
- Operations can review stored reports with `python3 backend/scripts/triage_support_requests.py` in an authorized environment.

The hosted API should configure:

```text
CIVORA_SUPPORT_CONTACT_URL=https://civoraai.com/support
CIVORA_BUG_REPORT_URL=https://civoraai.com/support?category=bug
```

These URLs prove an intake path. They do not prove staffing, response time, or escalation ownership.

## Hosted Operational Evidence

Provide credentials only through the process environment. Never put them on the command line or in a report.

```bash
CIVORA_EMAIL='...' CIVORA_PASSWORD='...' \
python3 backend/scripts/run_hosted_operational_evidence.py \
  --base-url https://api.civoraai.com \
  --expected-revision "$(git rev-parse HEAD)" \
  --output reports/release/hosted-operational-evidence.json
```

The report contains selected health, revision, storage, queue, support, and recovery facts. It never stores the credential or bearer token.

## Code Rollback Rehearsal

The safe rehearsal retrieves the previous revision into an isolated worktree and runs a focused verification command. It does not deploy, mutate the database, or change hosted infrastructure.

```bash
python3 backend/scripts/run_code_rollback_rehearsal.py \
  --candidate-revision HEAD^ \
  --output reports/release/code-rollback-rehearsal.json \
  --fail-on-blocked
```

An accountable operator must separately own and authorize any real Railway or Vercel rollback.

## Provider Backup And Restore

Do not mark hosted recovery ready until all of the following are real and recorded:

- Provider backups or point-in-time recovery are enabled.
- A named backup owner is accountable.
- Retention is at least seven days.
- Provider evidence is attached through an HTTPS URL.
- A restore drill has completed against an isolated target.
- The restored data has been validated without modifying production.

Enabling provider backups may affect billing or restart infrastructure. A real restore may destroy or replace data. Both require explicit operator authorization.

## Human Gates

Automation must not self-approve:

- Engineer UAT.
- Pilot terms, terms/privacy, or retention policy.
- Monitoring, escalation, rollback, and backup ownership.
- Billing provider activation or real charging.
- Public release.
- Professional approval or construction use.
