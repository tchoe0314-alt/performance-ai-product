# Concise controls website release — 2026-10-03

## Scope

The founder explicitly requested publication and post-release testing. Website candidate: `ee2055de42b3561eab8822257f911c2dfb693e26`, pushed only to `codex/phase-0-integration`. Includes the responsive control layout fixes from `5569e5ed` and concise Auth, Generate, and Deliver wording. Beta wording removed from Auth; invite-only access and compact engineering/export warnings remain truthful.

Backend and `main` remain unchanged. No purchases, paid imagery/generation, customer-project writes, or destructive actions are authorized by this release. Existing backend storage/recovery hold remains open.

## Pre-release proof

- Production-mode local build, TypeScript, modified-file ESLint, and diff checks passed.
- Fresh concise-control selection: 38 passed, no retries (25 seconds), covering responsive Draw/Deliver controls at five widths in Chromium/WebKit, Generate/Deliver mocked flow, onboarding/support, command behavior, and public workspace smoke.
- Additional local panel routing and export-staleness guards: 77 passed, no retries (26.8 seconds). Export guards are unit-level checks, not live export-job proof.
- An earlier selection had one outdated onboarding text expectation loaded before its test update. Its fresh targeted rerun passed; the final 38-test rerun above was clean.

## Hosting

- Candidate preview: `ESYPEMFrX2MMoWmD2XywXSsrqGSu`.
- Requested production rebuild: `A5RTyegMV9sGakw655FUQDhMAn2i`.
- Previous production deployment retained for rollback: `CVZLeydt1jbKQRUpkQJ35XSQV9tM`.
- Production rebuild **Ready**, duration 55 seconds, aliased to `civoraai.com`; immutable URL: `https://civora-bri4y3fkq-thomas-projects-3187b940.vercel.app`.
- Live `/api/release-identity` returns the exact candidate revision. API health is successful and still reports `597c46a3353f` on `main`.

## Post-release verification

- **96 passed, no retries (46.4 seconds)** against `https://civoraai.com`: responsive Draw/Deliver checks at 375/768/1024/1280/1440 pixels in Chromium/WebKit, all panel routes in both engines, onboarding/support, and public workspace smoke. Mock imagery explicitly selected; not real-provider imagery proof.
- Initial guarded real-backend selection: three passed; mobile WebKit completed its persistence and reload assertions but failed the strict page-error assertion with one API access-control message. Retained report: `/tmp/civora-concise-live-safe-report/index.html`. Browser network trace recorded the owned project POST requests as HTTP 200; this alone does not explain the page error or prove it harmless.
- Fresh unchanged mobile-WebKit test passed (4.3 seconds). Full guarded selection repeated separately: **all four passed, no retries (16.2 seconds)** on desktop Chromium/WebKit and mobile Chromium/WebKit. Report: `/tmp/civora-concise-live-safe-final-report/index.html`. The original failure is not suppressed or counted as a clean first run.
- Guarded checks register isolated synthetic accounts/projects, edit only their geometry, verify actual backend persistence and reload, and confirm protected API routes. No customer records, paid jobs, or deletion. Test records retained.
- Live layout evidence: `/tmp/civora-concise-live-results`; live UI report: `/tmp/civora-concise-live-report/index.html`.

## Remaining caution

The one-off mobile-WebKit page error remains an unexplained observation pending reproducibility; do not describe this release as universally bug-free. Backend production storage permissions and file recovery remain separate unresolved gates, unchanged by this website-only update. No complete paid generation/export/provider sweep was performed.
