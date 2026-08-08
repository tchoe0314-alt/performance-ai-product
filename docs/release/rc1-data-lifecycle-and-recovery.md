# Civora RC1 Data Lifecycle and Recovery

## Account Export

Authenticated users can request **Help > Account data > Download my data**. The ZIP contains `account-data.json` plus available user-owned project files and artifacts.

The export includes:

- public account profile;
- owned project records;
- shared-project membership metadata;
- organization memberships;
- project comments, review requests, and audit events visible to the user;
- memory/consent settings;
- job metadata;
- support requests;
- the user's chat-learning records;
- file paths, sizes, and SHA-256 hashes.

It excludes password hashes, password salts, auth tokens, cookies, API keys, and another user's private project content.

## Account Deletion

Deletion requires the current password and the exact confirmation phrase:

```text
DELETE MY CIVORA ACCOUNT
```

The readiness endpoint blocks deletion when the user owns a project with collaborators, has unresolved organization ownership involving other members, or has pending invitations that require ownership review. This prevents deletion from silently destroying shared work.

On a permitted deletion, Civora:

1. quarantines account-owned files;
2. deletes account-owned database records in a transaction;
3. removes or redacts account-specific learning records;
4. revokes authentication;
5. removes the quarantined files after the transaction succeeds;
6. restores quarantined files if the database operation fails.

If final filesystem cleanup cannot finish, the API reports `storage_cleanup_pending` instead of claiming complete deletion. Operators should inspect pending cleanup with a dry run:

```bash
PYTHONPATH=. python3 backend/scripts/cleanup_deletion_quarantine.py \
  --storage-dir "$PERFORMANCE_AI_STORAGE_DIR" \
  --older-than-hours 24 \
  --fail-on-pending
```

After confirming the listed directories are abandoned account-deletion quarantine data, repeat with `--confirm`. The tool only considers direct, non-symlink directories under `deletion_quarantine`.

## Local Backup/Restore Proof

Run:

```bash
PYTHONPATH=. python3 backend/scripts/run_backup_restore_drill.py \
  --output reports/release/rc1-local-backup-restore.json
```

The SQLite drill creates a backup, restores it to a separate database, and compares table row counts plus stable content hashes. This validates the local procedure only. It is not evidence of hosted provider backups.

## Hosted Backup/Restore Evidence

Hosted release gates require:

- `CIVORA_DATABASE_PROVIDER_BACKUPS_ENABLED=true`
- `CIVORA_DATABASE_BACKUP_OWNER`
- `CIVORA_DATABASE_BACKUP_EVIDENCE_URL`
- `CIVORA_DATABASE_RESTORE_DRILL_AT`
- `CIVORA_DATABASE_BACKUP_RETENTION_DAYS`

The evidence link should identify the database/provider, backup schedule, retention, encryption posture, restore target, restore date, owner, observed result, and any recovery-point/recovery-time limits. Configuration presence does not prove the provider operation; attach provider-side evidence.

## Retention Policy Decisions Still Requiring Human Approval

- project and upload retention after account closure;
- support request retention;
- audit-log retention;
- backup retention and deletion lag;
- legal hold behavior;
- export turnaround and identity verification;
- company ownership transfer;
- deletion exceptions required by law or contract.

Set `CIVORA_DATA_RETENTION_POLICY_READY=true` only after the responsible owner has accepted a written policy.
