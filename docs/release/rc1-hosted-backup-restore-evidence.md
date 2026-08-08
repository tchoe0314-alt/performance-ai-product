# RC1 Hosted Backup And Restore Evidence

## Scope

This record documents a non-destructive hosted PostgreSQL backup and restore drill for Civora's Railway production environment. It contains no database credentials, connection strings, access tokens, or customer record contents.

- Provider: Railway
- Drill date: 2026-08-08
- Production database service ID: `3608335e-8cc6-45e3-b6a9-a05c098dc9a0`
- Production environment ID: `309a9c56-d3f7-4879-bf75-621153d159f7`
- Accountable backup owner: configured founder/operator
- Production impact: none observed; the source service remained online throughout the drill

## Backup Configuration

The following provider-side controls were enabled and observed in Railway:

- PostgreSQL point-in-time recovery (PITR) with continuous WAL archiving.
- PITR coverage began at approximately `2026-08-08T15:16:39Z` and the archive head continued to advance during verification.
- The PITR storage bucket contained approximately 471.3 MB at the time of observation.
- Daily volume backups were enabled with Railway's displayed six-day retention.
- Weekly volume backups were enabled with Railway's displayed one-month retention.
- An immediate manual volume backup completed at approximately `2026-08-08T15:18:00Z` with a displayed size of 2.07 GB.
- Civora's configured recovery retention is 28 days, matching the approximate PITR recovery window documented by Railway. The shorter daily backup retention remains an additional recovery path, not the source of the 28-day claim.

Railway documents the provider behavior in [Backups](https://docs.railway.com/volumes/backups) and [Point-in-Time Recovery](https://docs.railway.com/volumes/point-in-time-recovery).

Encryption posture was not independently tested by this drill. Provider controls, encrypted transport, and access control remain part of Railway's managed service posture; this evidence does not make an independent cryptographic certification claim.

## Isolated Restore Drill

Railway restored the production database to a separate sibling service rather than replacing or modifying the source database.

- Requested restore point: approximately `2026-08-08T15:16:00Z`
- Restore completion recorded for Civora: `2026-08-08T15:20:12Z`
- Temporary restored service: `Postgres-restored-20260808-1516`
- Temporary restored service ID: `6cf2ce4f-be32-4f6a-a3a0-88a979f13b8c`
- Temporary restored volume ID: `03fe3efb-1370-40c1-8c98-6bcdd40475d9`
- Observed recovery time: under five minutes from restore confirmation to an online sibling service
- Observed recovery point: the provider-accepted point inside the displayed PITR coverage window

The observed recovery time and recovery point are drill results, not service-level guarantees.

## Integrity Verification

Both the production source and restored copy contained the same 15 public application tables.

| Table | Production rows | Restored rows |
| --- | ---: | ---: |
| `access_audit_log` | 134 | 134 |
| `auth_tokens` | 236 | 236 |
| `engineering_memory` | 0 | 0 |
| `jobs` | 234 | 234 |
| `memory_consents` | 0 | 0 |
| `organization_members` | 4 | 4 |
| `organizations` | 4 | 4 |
| `project_comments` | 0 | 0 |
| `project_invites` | 0 | 0 |
| `project_members` | 128 | 128 |
| `project_presence` | 1 | 1 |
| `project_review_requests` | 0 | 0 |
| `projects` | 128 | 128 |
| `support_requests` | 1 | 1 |
| `users` | 4 | 4 |

Additional deterministic comparisons matched:

- Canonical schema signature (columns, constraints, and indexes): `387e7e6485c0a429e9e9e0e2f95cfd89`
- Normalized PostgreSQL schema dump SHA-256: `fad64b5ddca503c6e4f5fe211c2c5c3ecd7c88181982a62cf71fd40549dd5f9c`
- Normalized PostgreSQL data dump SHA-256: `502d6217ef7aa0ff702aeff80c7c62e0b5a9606ed79ea08ff0dffd37bebeca1c`

The dump comparison removed comments, blank lines, and PostgreSQL's randomized `\restrict` and `\unrestrict` control tokens before hashing. It did not remove table data or schema definitions.

## Result And Limits

Result: provider backups are enabled, retention is configured, a separate restore completed, and the restored schema and data matched the production source at the selected recovery point.

Temporary restore cleanup completed at approximately `2026-08-08T15:40:00Z`. Railway removed the sibling service and its attached temporary volume from the environment after verification. The production database remained online, and its PITR bucket, backup schedules, and manual backup remained intact.

Truth boundary: this drill proves the selected hosted backup and restore procedure worked on 2026-08-08. It does not approve public release, legal terms, billing, engineering work, construction use, or future provider availability. Recovery drills must be repeated and owned operationally.
