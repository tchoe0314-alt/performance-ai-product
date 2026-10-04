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
