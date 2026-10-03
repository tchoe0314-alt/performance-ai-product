# Zero-additional-charge local staging

Established October 2, 2026 after the founder declined paid staging and requested a free setup. This is **local staging**, not an internet-hosted deployment or production approval.

## Running environment

- Website: `http://127.0.0.1:3042` (available only on this computer).
- API: `http://127.0.0.1:18882`.
- Fresh disposable storage: `/private/tmp/civora-free-staging.LyzYnr`. No customer database, production credentials or production files were copied.
- Source revision: `0109269057f4d8c7e00426624d0c940dd5b4afb1`.
- Frontend build: `.next-phase0-free-staging`, build ID `2BXWRQ6Z2GqHI3f4fyXSJ`.
- Backend started with a cleared inherited environment and explicitly disabled language, image, visualization and imagery-detection providers. No external provider credentials were supplied.
- Both servers bind to loopback. CORS permits only this staging website origin. Authentication and review-only construction guards remain enabled.
- This setup creates no additional cloud-hosting charges. It is not a new persistent cloud service; the servers must be running on this computer, and temporary test data is disposable.

## Cost decision

Read-only Railway account inspection showed a Pro subscription with $20 included usage and $0.63 current usage for October 1–November 1. That shared allowance does not guarantee a new hosted environment will cause zero additional charges. No Railway environment/service/database/volume was created, no Vercel deployment was triggered, and no repository push was performed. Production is unchanged.

## Verification and limits

The production frontend build passed. Fifteen isolated backend lifecycle, backup/restore and legacy-database preservation tests passed. Real-local signed-in export/download and save/reopen/owner-isolation browser checks run with both API and website explicitly targeted at this fresh localhost environment; report output is `/tmp/civora-free-staging-proof`.

This does not prove hosted configuration, shared Postgres worker operation, provider backups, public networking, real map/imagery correctness, external CAD interoperability or engineering accuracy. The immediate mobile-WebKit refresh-after-download edge remains separately recorded. Phase 0.2 stays open for required external evidence.

The initial eight-case collection recorded seven passes and one registration-rate-limit rejection (HTTP 429) after rapid synthetic account creation. All four browser export/download cases passed; desktop Chromium/WebKit and mobile Chromium persistence cases passed. The API's registration protection was not disabled or relaxed. The remaining mobile-WebKit persistence case was rerun separately after restarting only this disposable local API, retaining its database: **one passed, zero failed, zero skipped**, 2.5 seconds. The isolated report is `/tmp/civora-free-staging-rate-isolated-proof`. This does not retroactively make the original combined collection all-green.
