# Local release compatibility gate

This gate creates safe repository and disposable-service evidence. It never proves a hosted release by itself and never changes Vercel, Railway, a hosted database, or customer data.

## Inputs that must be known

- Candidate SHA: the exact revision being built for frontend, API and worker.
- Deployed SHA: the exact revision currently serving all three components.
- Rollback SHA: a previously proven, recoverable revision—not merely `HEAD^`.
- Provider evidence, collected separately and read-only: frontend/API/worker deployment IDs and SHAs, shared database identity, backup timestamp/retention, worker readiness, and rollback controls.

If either deployed or rollback SHA is unknown, keep the release decision **NO-GO**.

## Run the local gate

Use a clean detached worktree at the candidate SHA:

```bash
python3.11 backend/scripts/run_local_release_compatibility.py \
  --expected-revision <candidate-sha> \
  --deployed-revision <current-hosted-sha> \
  --rollback-revision <last-known-good-sha> \
  --run-disposable-tests \
  --output /tmp/civora-local-release-compatibility.json
```

The disposable check covers legacy SQLite startup/migration behavior, database pooling and API release-safety guards. The report separately states whether the compared release introduced schema-related files or added DDL. A clean result does not erase Civora's preexisting risk from runtime additive DDL without a migration ledger.

Then rehearse retrieving and testing the exact rollback SHA without changing the active tree or database:

```bash
python3.11 backend/scripts/run_code_rollback_rehearsal.py \
  --current-revision <candidate-sha> \
  --candidate-revision <last-known-good-sha> \
  --output /tmp/civora-code-rollback-rehearsal.json \
  --fail-on-blocked
```

## Hosted go/no-go criteria

GO requires all of the following for one exact candidate SHA:

1. Local compatibility report has no blockers and its schema conclusion has been reviewed.
2. Frontend release identity, API deployment and worker artifact all match the candidate SHA.
3. API and worker prove the same database/storage identity; liveness alone is insufficient.
4. Restored disposable backup boots with the candidate and passes save/reload, queue completion and calculated export checks.
5. Authenticated hosted canary passes project creation, canonical save/reload, Generate, worker completion, Review freshness and guarded downloads.
6. Last-known-good SHA, deployment IDs, backup timestamp and rollback owner are recorded.
7. Rollback rehearsal passes, and provider rollback controls plus post-rollback canary steps are confirmed.

Any mismatch, missing identity, failed compatibility check, unknown rollback target, absent backup, stale worker or unverified schema transition is NO-GO. Never replace those facts with a local pass.

## Current repair series schema boundary

The final chat/Review commit `66a42aca` changes frontend files only. Whether the complete release introduces schema changes must be computed from the actual currently deployed SHA to `66a42aca`; the deployed SHA is a provider fact. Runtime DDL and the lack of versioned/down migrations predate this final commit and remain release risks even when the compared diff contains no schema change.
