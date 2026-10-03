# Phase 0 website deployment — 2026-10-03

## Authority and scope

The founder explicitly approved deployment in this chat. Existing no-purchase and customer-data protections remain in force. The candidate is `837787d891a75f4071ecd36b95f6a489564bb175`, pushed to `codex/phase-0-integration`; `main` was not changed.

This is a **website-only release using the existing production API**, not a paired backend release or Phase 0 completion. The API image's restricted-user change must not be deployed until existing mounted storage permissions and recovery are verified. No production volume ownership changes, database restores, new subscriptions, additional hosted services, or paid AI jobs were requested or performed.

## Exact candidate CI

- [Linux container verification](https://github.com/tchoe0314-alt/performance-ai-product/actions/runs/37163072665): success on the exact candidate; both Dockerfile/8002 and Dockerfile.backend/8080 jobs passed. These use disposable, permission-prepared volumes, not the production mount.
- [Firefox accessibility](https://github.com/tchoe0314-alt/performance-ai-product/actions/runs/37163081454): success on the exact candidate. This is the workflow's focused accessibility scope, not the entire Firefox feature suite.

## Hosting record

- Previous production website: `3CRV4fpF3sLWazAoYnDfrhtFY23A`, source `597c46a3353f3a58b70925f74d753a679c8ce3de`.
- Candidate preview: `A1KDu9DLgW1P8XUGbLVHEPMWCLp3`, Ready after 1m 6s.
- Production deployment through the existing Vercel project: `CVZLeydt1jbKQRUpkQJ35XSQV9tM`, **Ready** after 1m 18s, attached to `civoraai.com`. Vercel rebuilt this promotion using production environment settings. Its immutable deployment URL is `https://civora-drquf3kfs-thomas-projects-3187b940.vercel.app`.
- Existing Railway API tracks `main` with Wait for CI disabled. Pushing the candidate branch did not request a production API replacement.
- Existing Postgres backups observed: latest weekly snapshot about nine hours old, 2.71 GB; daily snapshots present; PITR coverage shown from September 12 through October 3. No restore was initiated. Backup availability is not a current exact-candidate restore proof.
- API file-storage volume shows **no scheduled backups**. Live mount permissions could not be verified through Railway's console, which displayed no running instances/disconnected. Backend promotion remains held.

## Post-release verification

- Live `https://civoraai.com/api/release-identity` returns HTTP 200 JSON with full revision `837787d891a75f4071ecd36b95f6a489564bb175` and known status.
- Live API health returns HTTP 200/success with unchanged production revision `597c46a3353f`, branch `main`.
- **Four guarded authenticated live tests passed, no retries**: desktop Chromium/WebKit and mobile Chromium/WebKit. Each registered a separate synthetic test account/project, moved the synthetic office from X=100 to X=125, observed actual API persistence, refreshed, verified X=125 and unchanged dimensions, checked workspace panels, and verified protected endpoints reject unauthenticated requests. No generation, imagery, export jobs, customer-project mutations or deletions were permitted. The two previously failing mobile cases now pass with the same test/assertions. Duration about one minute.
- **One public workspace test passed, no retries**: shell, core controls, panels, 2D/3D switching, and explicitly mocked visual-concept mode. This is not a real imagery-provider quality or paid-provider proof. Duration 25.8 seconds.
- Local reports: `/tmp/civora-phase0-deployed-safe-report/index.html` and `/tmp/civora-phase0-deployed-public-report/index.html`. Evidence images under `/tmp/civora-phase0-deployed-safe-results`. Synthetic records were retained in their own accounts, not deleted.

## Remaining proof / operational caution

Live mounted-file permissions, file-storage backup/recovery, and exact hosted recovery verification remain open before backend promotion. The database has current backup/PITR coverage, but availability does not replace a tested restore. A website-only release leaves frontend/API source revisions different and must not be reported as a successful paired-release canary or completion of Phase 0. `main` still identifies the old paired baseline; a future push to it will automatically deploy Railway and could replace the manually promoted website, so do not push it until the backend release hold is resolved. Prior website deployment ID is retained above for rollback; no provider rollback was exercised during this release.
