# Phase 0.5 — Release preparation checkpoint

October 3, 2026. **Local preparation advanced; not deployment approval or Phase 0 completion.**

## Candidate and proof

Website baseline: `c273e2e3265b09f2ab81a8d4a28e1ceb10e87885`. Final 0.4 website artifact and its 736 passing checks/13 documented exclusions remain in the [maintainability closeout](../product/phase-0-maintainability-review.md). This pass changes only the SQLite recovery service, its tests and documentation; it does not rebuild or certify a new deployed website/API.

- Initial migration, lifecycle/recovery, release-readiness, API-safety and cleanup selection: 53 passed, seven subtests passed, one existing dependency deprecation warning.
- After the capacity safeguard: the same affected selection passed **55 tests and seven subtests**, 1.22 seconds, one existing warning. Includes successful isolated SQLite content/schema/integrity roundtrip, legacy geometry/results preservation through repeated startup, full-disk rejection before copying, and rejection when a shared disk can fit only one copy. This is not hosted PostgreSQL evidence.
- Separate startup/worker-health/validation-runner contracts: **31 passed**, 2.47 seconds. Startup cases use mocked executables; worker-health cases use an isolated local HTTP server. They do not substitute for container execution.
- Rollback retrieval rehearsal: current `c273e2e3`, candidate `b0e536156d1785100f99eab377b695c99a084358`, clean isolated checkout, critical paths present, release-safety/readiness verification exit zero. Report: `/tmp/civora-phase05-code-rollback-c273e2e3.json`. The temporary checkout was removed by the runner. No provider rollback, database downgrade or old-version/new-data compatibility proof is implied.
- Changed recovery module scanned with existing isolated Bandit 1.8.6 runtime: zero findings, existing SQL-identifier suppression annotations retained. The initial backend runtime lacked Bandit; the separate audit runtime was used instead, not treated as a passing missing-tool check.
- Whitespace checks pass. Source SHA-256: `backend/services/backup_restore.py` = `85b27c3f94916f6b16ba6c459f177fa34d8115c432b0d05a9c0d585b50f3322d`; affected test = `9fe3a8f0dd9b88649e8c7a80ad0a69725c269fe284565dd543c5d93b24bd7ce8`.

These scopes overlap; do not sum them into a unique or complete backend-suite count. Only affected tests were rerun after this recovery-only change.

## Disk-capacity defect and disposition

The disposable local staging SQLite database was 911,523,840 bytes. An initial real-size drill was interrupted when available disk space was insufficient for backup plus restore copies. It is not passing recovery evidence. Only that run's generated, unverified backup and two SQLite sidecars were removed; original staging database, customer data, source files and prior reports were untouched. These temporary copies are regenerable from the retained source.

Recovery now checks backup and temporary-restore filesystem capacity before copying, accounting for database/WAL size, two copies on a shared filesystem and 64 MiB headroom. Low capacity returns a structured blocked report and a nonzero CLI exit with `--fail-on-blocked`. Actual oversized-target preflight correctly blocked with no copy started: `/tmp/civora-phase05-capacity-proof.json`. A capacity estimate is not a reservation; concurrent writes/disk usage may still change. Large-database content hashing currently materializes table rows, so production-scale memory/performance testing remains required. Do not claim the oversized drill completed.

## Next gates, existing resources and required decisions

| Gate | Available path | Still missing |
| --- | --- | --- |
| Firefox | Existing `.github/workflows/rc1-firefox-accessibility.yml` on Linux | Exact-candidate successful run or explicit founder-approved pilot exclusion. Founder asked; no exclusion assumed. This workflow proves its accessibility/navigation selection, not every Firefox workflow. |
| Container runtime | Existing `.github/workflows/backend-container-runtime.yml`, both backend images, disposable fresh/restarted volume | Exact-candidate CI result. Docker/Podman are unavailable locally. Current verifier covers permissions/auth/projects/uploads/artifact access/worker; separate hosted export and restored-data migration checks remain required. |
| Hosted identity/auth/workers/exports | Existing Vercel website, Railway backend and canary/hosted tests | Approved exact candidate target and deployment, dedicated synthetic account, frontend/API/worker revision IDs, persisted editing/reopen/owner-isolation/export/job evidence. Local 736-pass result is not hosted proof. |
| Hosted backup/restore/rollback | Existing provider procedure and August 8 drill record | Current configuration evidence, isolated candidate-compatible restored target and provider rollback evidence. Previous drill is historical; do not re-enable billing controls or replace production data without approval. |
| Security/tool support | Existing advisory register and audits | Unpatched development-only braces advisory and unsupported lint-major lifecycle disposition; final hosted dependency/static scans. No waiver assumed. |

No CI dispatch, push, deployment, new cloud resource, paid provider call or purchase occurred. Existing CI checks are possible next steps, but available account minutes/cost and push-triggered deployment effects must be established before dispatch/push. Do not assume that an existing subscription guarantees zero incremental cost.

The founder previously declined a paid/separate hosted staging environment. Keep the current backend; do not invent a new backend requirement. Production read-only checks can inspect current health/identity, but cannot prove this undeployed candidate. Any hosted restore/destructive synthetic tests require an isolated target; ordinary approved production smoke checks must avoid customer-data mutations. If candidate verification is to occur on the existing live environment, request explicit deployment approval with rollback and safe smoke scope rather than silently calling it staging.
