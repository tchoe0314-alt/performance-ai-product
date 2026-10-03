# Current website/backend — narrowly authorized live checks

Recorded October 2, 2026. The founder explicitly authorized using the existing backend for website checks after declining paid separate staging. This does not authorize backend deployment, destructive tests, paid AI/imagery calls or access to customer projects.

## Actual target and scope

- Website: `https://civoraai.com`.
- API: `https://api.civoraai.com`.
- Health before and after initial checks: HTTP 200, Postgres available, private-alpha/review-only guards enabled. API-reported revision: `597c46a3353f`, branch `main`, production. This is not the newer local integration revision and does not establish the exact frontend revision.
- Newly created synthetic accounts only; projects are named `CIVORA TEST ONLY <suffix>` and marked synthetic/test-only. No customer records or existing user credentials were used. Test records are retained; no account/project deletion was performed.
- Browser write guard forwards only saves to the current synthetic project and its presence endpoint. Other writes are rejected by the harness rather than forwarded. No blocked-write attempt was recorded in the initial passing collection.
- No generation, imagery, export jobs, paid-provider calls, deployment, repository push or hosting-resource creation was performed. This is bounded functional checking, not a load/stress test.

## Initial evidence

`hosted-current-backend-safe.spec.ts` passed once per desktop Chromium/WebKit and mobile Chromium/WebKit, four cases total. Real registration/login and protected API access succeeded. Each case opened its synthetic project, changed the office x coordinate from 100 to 125, observed the actual API persist that value, refreshed and verified restoration, and opened Setup/Generate/Review/Deliver without triggering generation. Anonymous project/jobs access was rejected and no uncaught browser error was recorded.

Reports: `/tmp/civora-current-backend-safe-proof` and `/tmp/civora-current-backend-safe-devices`. The first fixture used legacy dimension names in native site-object data; it verifies coordinates, not full building dimensions. A stricter follow-up uses native `w`/`d` and explicitly verifies width/depth; report output is `/tmp/civora-current-backend-final-safe-proof`. Do not treat the initial coordinate-only result as proof of that additional path.

The harness requires `CIVORA_PRODUCTION_SAFE_TESTS=1` and exactly `PLAYWRIGHT_BASE_URL=https://civoraai.com`. It does not run write checks by default. Device scope is narrowed to this safe suite when this explicit flag is enabled. A production-backed preview, release migration, full workflow certification or deployment readiness is not proven by these checks.

## Stricter follow-up result

The first full-dimension follow-up stopped with one failure and three unrun cases: the object-list Select control was hidden after the disclosure collapsed during selection. The screenshot showed the actual 160-by-90-foot object present. The helper now checks visibility and reopens the disclosure using its normal summary control, both before Select and before Inspect; no forced clicks or product/deployment changes were used. The fixture now uses the native `office_building` type and `w`/`d` fields.

Final result: **four passed, zero failed, zero skipped**, 17.7 seconds, desktop Chromium/WebKit and mobile Chromium/WebKit. Each verifies x=100 initially, width=160 and depth=90, changes x to 125, confirms backend persistence, refreshes and confirms all three values, then opens the four workflow panels. No blocked background-write attempt or uncaught browser error was recorded. Final screenshots visually show the placed building in the live website. Report: `/tmp/civora-current-backend-geometry-safe-proof`.

Scoped lint and TypeScript checks passed. Nine synthetic test accounts/projects were created across all collections and retained. These are test-only records, not customer accounts; no deletion, export, AI generation, new paid service or deployment was performed. This report records both failed and passing collections, not a retroactive all-green result for the earlier failure.
