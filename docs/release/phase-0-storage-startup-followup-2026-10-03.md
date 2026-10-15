# Phase 0.5 — consistent backend storage startup protection

## Change

The alternate `Dockerfile.backend` previously launched Uvicorn directly, bypassing the runtime-directory permission checks used by the primary image. Both now call `scripts/check_backend_storage.sh`. The alternate entrypoint preserves single-process Uvicorn and its 8080 default, while respecting an explicitly configured `PORT`.

The guard requires writable/searchable storage and renderer directories before starting a service. It creates missing runtime directories as before, but never changes existing permissions or ownership. Existing worker/combined/web routing remains unchanged. This is startup protection, not a proof that existing uploaded files or nested directories are writable.

Linux CI now checks that both images fail promptly against a deliberately inaccessible **disposable CI volume**, preserve its root ownership, then pass the existing fresh/restored-volume checks after that disposable volume is prepared. No production permission change is part of the workflow.

## Verification

- Startup and legacy migration selection: **20 passed** (1.09 seconds), including both startup paths rejecting file/read-only runtime paths, alternate default/custom port behavior, all existing primary process-routing tests, and legacy migration preservation.
- Combined runner and worker health: **10 passed** (1.34 seconds).
- Shell syntax and whitespace checks passed.
- Real alternate-wrapper startup with fresh isolated SQLite storage and providers disabled succeeded; HTTP health reported success. Process stopped normally afterward. Test storage retained at `/private/tmp/civora-phase05-startup.wqcgUN`.
- Docker is unavailable locally; the updated Linux container scenario has **not yet run**. Prior Linux evidence certifies the earlier image, not this changed candidate.

## Current Phase 0.5 gate

Website deployment and guarded desktop/mobile authentication/save/reload are verified in the October 3 release records. Website remains `ee2055de42b3561eab8822257f911c2dfb693e26`; production backend remains `597c46a3353f`. This follow-up is local only: no deployment, main push, paid calls, new services or production data/permission changes.

Remaining before closing 0.5: exact revised Linux image verification; production mount ownership and nested-file access evidence; file-storage backup/recovery; isolated hosted database restore/migration/rollback verification; and paired frontend/backend exact-artifact verification after a separately approved backend release. A website preview using the production API is not isolated staging. Local passing checks do not close those gates.

## Hosted checks and Linux follow-up

- Scoped change committed/pushed only to the integration branch, initially `7ffd17feb82dbad1831a590c9b04f251f2e70ae2`. No `main` push or production promotion.
- First Linux run [37167380747](https://github.com/tchoe0314-alt/performance-ai-product/actions/runs/37167380747) failed in both inaccessible-storage fixtures. Diagnostics added at `9849768272a45888e50e4c9d92d5ed13954bd46a`; second run [37167505611](https://github.com/tchoe0314-alt/performance-ai-product/actions/runs/37167505611) also failed. Retained artifact confirmed `/data` was actually `10001 10001 755`, not the intended `0 0 700`, before the supposedly blocked startup. Docker reinitialized the empty volume from the image directory, invalidating the fixture. Timeout is not passing startup protection.
- At `df0443298b4846e6e4b1858043106450e3055e80`, the fixture is kept nonempty and its actual owner/mode asserted before starting. Failed-job artifacts are retained and temporary blocked containers explicitly cleaned up. Corrected run [37167648629](https://github.com/tchoe0314-alt/performance-ai-product/actions/runs/37167648629) **passed both images**. Downloaded artifacts inspected: actual blocked mount `0 0 700`, startup-blocked message present, fresh/restored reports both passed with UID 10001 and health/permissions/auth/projects/uploads/artifact-access/worker checks. These are disposable Linux-volume results, not production-mounted-file proof.
- Combined affected local startup/migration/runner/worker selection: **30 passed** (2.81 seconds), no exclusions. Workflow syntax parsed with the existing `js-yaml` dependency; shell syntax/diff checks pass.
- Railway read-only recheck: all five services online. API console still shows **No running instances / Disconnected**; live mount ownership and nested access could not be inspected. API file-volume backups show **No backup schedule** and **No Backups**; mount `/data`, configured maximum 50 GB (not measured usage).
- Postgres backup screen shows daily/weekly snapshots (latest weekly approximately ten hours old, 2.71 GB), and PITR coverage September 12 through October 3 20:16 local time. No restore started. This is availability, not exact-candidate isolated restore proof.
- Railway [backup documentation](https://docs.railway.com/volumes/backups) states incremental backup storage is billed. No backup creation/schedule or restore/new-service action performed under the standing no-additional-spend instruction.
