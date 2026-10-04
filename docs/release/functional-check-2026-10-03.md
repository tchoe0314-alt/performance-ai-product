# Functional website check — 2026-10-03

User requested actual functionality verification after publication. No application changes or further deployment were made. Live website identity remains `ee2055de42b3561eab8822257f911c2dfb693e26`.

## Results

- **83 passed, zero retries, 1.4 minutes**: live-site functional selection, Chromium plus opted-in WebKit cases. Drawing, site-boundary finish, exact coordinates, snaps, transforms, object manager, layers, groups, selection, copy/paste/delete, recovery history, native road/pipe edits and JSON import, controlled Generate/Deliver behavior, and recorded-video regression. Browser cases exercise the deployed website's UI; several tests explicitly mock API responses. Two seed checks are unit cases. This is not all 83 cases on both browsers or all real-backend execution. Report: `/tmp/civora-functionality-live-report/index.html`.
- **4 passed, zero retries, 23.4 seconds**: real local authentication, save/reload, account isolation, preliminary PDF/DXF job completion and browser downloads in Chromium/WebKit. Valid PDF signature; DXF preliminary warning/source revision/stale-system content; denied anonymous/other-owner downloads; download does not replace workspace navigation; artifact history survives reload. Report: `/tmp/civora-functionality-files-report/index.html`.
- **60 passed, zero retries, 5.5 seconds**: 58 source-level object-rulebook/detailed-geometry tests and two live website browser cases with controlled backend responses checking generated requests contain drawn, placed and newly combined objects. Collision coverage includes pipe profiles, foundation and pier crossings, missing/unreviewed evidence, clearances, unit conversion, setbacks, concave boundaries, stale evidence and JSON restore. Report: `/tmp/civora-functionality-context-report/index.html`.

## Local test environment

Existing agent-owned baseline server at localhost:3042 was stopped and replaced with the current concise-controls production-mode artifact `.next-aesthetics-pass`, using the existing disposable localhost:18882 API. This provides the API's configured allowed local origin; no production CORS change. This build predates the copy-change commit but contains the released application changes. Local API is the pre-existing disposable SQLite runtime, not the hosted API revision or a newly attested backend build.

## Limits

No failures or new reproducible bugs in these selections. No paid AI/imagery requests, live export jobs, customer-project writes, deletions, or production backend modifications. The earlier one-off live mobile-WebKit API access-control page error remains recorded in the deployment report; these selections do not resolve its cause. Real provider output quality, hosted export worker execution, professional engineering acceptance, and production storage/recovery remain separate unproven scopes. Recent guarded live save/reload proof remains in the deployment report; not rerun in this selection.

## Follow-up recovery and session checks

- **80 passed, zero retries, 55.6 seconds**: live-site Chromium plus opted-in WebKit cases covering invalid login, expired/unavailable sessions, failed/empty image detection, upload validation, uncertain geocoding, source-provider failures, chat retry guidance, loading state completion, responsive controls, linked-building/parking edits and undo, fixed geometry, outdated layout proposal rejection, and 2D/3D parity. Contains source-level unit tests and explicitly mocked provider/backend failures; not all cases run on both engines. Report: `/tmp/civora-recovery-live-report/index.html`.
- **3 passed, zero retries, 27.1 seconds** on the disposable local website/API: small-site human-click workflow, 40 concurrent synthetic project writes with cross-account read isolation, and two authenticated windows through 24 panel-switch cycles plus repeated preview quality/2D/3D changes. Existing responsiveness/heap thresholds unchanged. This is a bounded stress scenario, not hours-long soak or hosted capacity certification. Report: `/tmp/civora-sustained-local-report/index.html`.
- Application source, production deployment, provider settings, and customer records unchanged during this follow-up.
- **1 passed, zero retries, 2.5 seconds**: real local UI sign-in, tab-scoped credentials, reload restoration, separate-tab isolation, sign-out clearing and signed-out reload. Report: `/tmp/civora-session-followup-report/index.html`.
