# Phase 0 release procedure — not release approval

This procedure supplements the RC1 operations/recovery runbooks. It does not establish that staging exists, authorize a deployment, or approve production promotion. Current integration branch: `codex/phase-0-integration`; release revision and deployment IDs are pending.

## Environment separation

- Development validation uses localhost, disposable storage and disabled AI/image providers. Current local checks use port 3042 for the frontend and 18882 for the API. These addresses are not release configuration.
- Staging must have a separate database, storage volume, queue and frontend/backend origins. Never point staging jobs, deletion tests or restore drills at production storage. Start with synthetic accounts/projects and providers disabled unless separately authorized.
- Production retains its own accounts/data and credentials. Do not copy production credentials into test commands or checked-in files. Public frontend variables are not a safe place for secrets.
- An operator must configure allowed origins, API address, product mode, worker/shared-database settings, support and recovery ownership using the deployment/runbook instructions. Record variable names and configuration checks, never secret values.
- Staging and production deployments each require explicit user approval; provider enablement, paid calls and backup changes with billing implications also require approval.

## Database compatibility and migration

The current database initializes tables and applies additive compatibility changes during startup; it does not use a versioned migration ledger. Existing projects may receive `has_result`, organization and lifecycle columns; jobs may receive stage/detail/progress columns. JSON project geometry is not intentionally converted by these startup changes. Phase 1 schema conversion is not part of this release.

1. Record the current code/deployment revision, database type, storage location and responsible operator. Inspect the startup changes for the exact candidate diff.
2. Take a consistent database backup and preserve uploads/artifacts using the existing recovery procedure. Verify recoverability before allowing candidate startup against valuable data.
   The SQLite drill checks capacity for backup and temporary restore copies (including WAL and headroom) before copying. A blocked capacity report is not recovery proof. Capacity may change during execution; allow additional space and validate large-database memory requirements. Record an interrupted drill as interrupted, not passed.
3. Restore into an isolated target with no production job access. Start the candidate there first. Compare project/user/job counts, serialized project geometry/results, file hashes and integrity checks. Confirm owner access and rejection of unauthorized access.
4. Run candidate startup twice and confirm additive changes are idempotent. `tests/test_phase0_legacy_database_migration.py` verifies preservation and repeated startup on an older synthetic SQLite schema; it is not Postgres or customer-data migration evidence.
5. Verify both a fresh database and the restored older database with real login, save/reopen, upload/export and queue completion. Hosted Postgres requires its own restored-target evidence; fake connections and SQLite tests cannot supply it.
6. Stop promotion on migration, integrity or compatibility failure. Do not drop columns, rewrite project JSON or substitute invented coordinates to get a passing gate.

## Rollback

Code rollback and data restore are different operations. Additive schema changes do not prove older code can read newly saved data. Verify the previous version against an isolated upgraded database first. Use the existing code rollback rehearsal for revision retrieval/testing; it does not perform or prove a provider rollback.

If old code is compatible, an authorized operator may redeploy the recorded prior artifact. If restoring pre-release data is necessary, explain possible loss of newer writes and obtain explicit approval before replacing data. Preserve the failed candidate data for investigation. Never infer database downgrade permission from deployment approval.

## Exact-build gate and release record

- Produce a clean, scoped integration commit without adding unrelated investor artifacts or secrets. Record commit, lockfile/requirements hashes, source inventory fingerprint and frontend build ID.
- Record full backend/browser results, affected regressions, lint/type/build, dependency/static scan scope, skips and known limitations for that artifact. A targeted rerun does not change a failed original full-run result.
- Prepare staging approval with target, scope, costs/provider status, migration/backup evidence, rollback candidate and post-deployment checks. Deploy only after approval.
- Verify deployed frontend/backend revision identity plus real authentication, project save/reopen, owner isolation, object editing, alternatives/apply/undo, exports and worker completion on staging. Record deployment IDs and report links.
- Request production approval separately, then verify production identity and safe smoke workflows after promotion. Do not run destructive synthetic account tests against real users.
- Keep Phase 0 open while exact-build deployment evidence is missing. Local passing tests alone are insufficient. Independent engineering/provider/CAD evidence remains separately disclosed and is never implied by software release checks.

Versioned release notes should list the approved revision, changes, proven workflows, compatibility impacts, limitations, unresolved provider/engineering evidence and rollback instructions. No release version is assigned here while integration and hosted verification remain unfinished.
