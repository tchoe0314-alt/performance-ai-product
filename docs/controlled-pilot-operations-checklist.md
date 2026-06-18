# Controlled Pilot Operations Checklist

Use this checklist to launch and run a small, controlled Civora pilot. This is an internal operations document, not a construction release checklist.

Permanent responsibility rule: Civora never stamps, seals, signs, certifies, approves construction, submits construction documents, or acts as engineer of record. Only the licensed engineer or user can review, approve, stamp, seal, sign, submit, and take legal responsibility.

For the business-operations packet covering access flow, roles, support, bug intake, data retention/deletion, confidential input, usage limits, billing readiness, and pilot terms, use [pilot-business-operations.md](/Users/tommychoe/Documents/Playground/Civora%20AI/docs/pilot-business-operations.md).

## Pilot User List

Maintain a private pilot roster before invites go out:

| Field | Required |
| --- | --- |
| User name | Yes |
| Company/team | Yes |
| Email | Yes |
| Role | Yes |
| Licensed engineer? | Yes/No/Unknown |
| Pilot cohort | Yes |
| Support contact owner | Yes |
| Invite status | Not invited / Invited / Active / Paused / Removed |
| NDA or pilot terms accepted | Yes/No |
| Allowed project type | Test-only / Internal feasibility / Other approved scope |
| Notes | Optional |

Do not invite users without a named internal owner and support path.

## Pilot Invite Process

1. Confirm the user is on the approved pilot roster.
2. Confirm pilot terms, confidentiality expectations, and review-only scope.
3. Send the invite with the app URL, onboarding guide, support contact, and known limitations.
4. Tell the user to start with non-confidential or approved test inputs.
5. Confirm the user understands exports are review packages unless externally approved by a licensed engineer outside Civora.
6. Confirm Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.
7. Mark the roster invite status as `Invited`.
8. After first login and first project creation, mark the status as `Active`.

## Required Env Vars

Backend:

| Variable | Required | Notes |
| --- | --- | --- |
| `CIVORA_AI_PROVIDER` | Yes | Use `openai`, `none`, or `ollama`. `none` uses deterministic/local fallback behavior. |
| `OPENAI_API_KEY` | If provider is `openai` | Keep out of logs and screenshots. |
| `PERFORMANCE_AI_STORAGE_DIR` | Yes | Must point to persistent storage in deployed pilot environments. |
| `CORS_ALLOW_ORIGINS` | Yes | Use explicit frontend origins. Do not use `*` for private pilot or production. |
| `MAPBOX_TOKEN` | If address/geocode support is enabled | Address lookup is review context only, not source trust by itself. |
| `CIVORA_OLLAMA_BASE_URL` | If provider is `ollama` | Required only for local model mode. |
| `CIVORA_CHAT_MODEL` | Optional | Set when overriding default chat model. |
| `CIVORA_COMMAND_MODEL` | Optional | Set when overriding default command model. |
| `CIVORA_CAD_ASSISTANT_MODEL` | Optional | Set when overriding default CAD assistant model. |
| `CIVORA_ALLOW_LOCAL_PILOT_CORS` | Temporary only | Use only for short QA windows where local frontend calls live backend. Remove afterward. |
| `CIVORA_LOCAL_PILOT_CORS_ORIGINS` | Temporary only | Pair with `CIVORA_ALLOW_LOCAL_PILOT_CORS`. |
| `CIVORA_MAX_IMAGE_UPLOAD_BYTES` | Recommended | User-facing image/map upload limit. Default is 10 MiB. |
| `CIVORA_MAX_SURVEY_UPLOAD_BYTES` | Recommended | User-facing survey CSV upload limit. Default is 5 MiB. |
| `CIVORA_MAX_EXISTING_CONDITIONS_UPLOAD_BYTES` | Recommended | Existing-condition and plan PDF upload limit. Default is 25 MiB. |
| `CIVORA_SUPPORT_CONTACT_URL` or `CIVORA_SUPPORT_EMAIL` | Required before public beta | User-visible support path exposed through safe health metadata. |
| `CIVORA_BUG_REPORT_URL` | Required before public beta | User-visible bug intake path. |
| `CIVORA_ESCALATION_CONTACT` | Required before public beta | Internal owner for safety, source-trust, privacy, billing, and export incidents. |
| `CIVORA_MONITORING_OWNER` | Required before public beta | Named owner for deployment health, queue, auth, upload, and error monitoring. |
| `CIVORA_ROLLBACK_OWNER` | Required before public beta | Named owner authorized to roll back or disable Vercel/Railway services. |
| `CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN` | Required before public beta | Keep `false` until all support, privacy, billing/legal, production storage/queue, monitoring, rollback, and review-only gates are owner-accepted. |

### Local Private-Alpha Readiness Defaults

Use these defaults for local browser QA and backend readiness checks:

```bash
export CIVORA_PRODUCT_MODE=private_alpha
export CIVORA_DEPLOYMENT_TARGET=local
export CIVORA_FRONTEND_PUBLIC_URL=http://localhost:3000
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8002
export CIVORA_PUBLIC_API_BASE_URL=http://127.0.0.1:8002
export CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
export PERFORMANCE_AI_STORAGE_DIR=./data
```

Local private-alpha CORS must include both `http://localhost:3000` and `http://127.0.0.1:3000` so browser QA can use either frontend origin against the local backend. Public beta and production must continue to use explicit deployed HTTPS origins and must not use wildcard CORS.

Queue monitoring evidence is not faked by local scripts. A no-URL run of `PYTHONPATH=. python3 backend/scripts/run_private_alpha_readiness.py` can complete and write a blocked report, but it does not clear private-alpha readiness. To clear the queue blocker, start a live backend with the runtime debug endpoint available, configure a valid audit token, then run:

```bash
export CIVORA_RUNTIME_DEBUG_BEARER_TOKEN=<valid backend bearer token>
PYTHONPATH=. python3 backend/scripts/run_private_alpha_readiness.py --base-url http://127.0.0.1:8002 --runtime-bearer-token "$CIVORA_RUNTIME_DEBUG_BEARER_TOKEN" --fail-on-blocked
```

Passing queue evidence must come from `/api/debug/runtime` and include `JobQueueService.runtime_stats()` data with monitored job types plus pending, failed, stale/timeout, and worker/runtime confidence fields. If that endpoint or token is unavailable, mark readiness blocked and attach the generated report instead of marking readiness green.

Frontend:

| Variable | Required | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Must point to the intended backend URL. |

Billing:

| Variable | Required before charging | Notes |
| --- | --- | --- |
| `CIVORA_PAID_PILOT_MODE` | Yes | Enables paid-pilot status only; it does not collect payment by itself. |
| `CIVORA_ENABLE_REAL_CHARGING` | Yes | Must be explicit and paired with legal docs plus provider config. |
| `CIVORA_BILLING_LEGAL_DOCS_READY` | Yes | Set only after owner/counsel approval of terms, privacy, order form, and billing language. |
| `CIVORA_BILLING_PROVIDER` | Yes | `none` keeps payment disabled. |
| `STRIPE_*` | If provider is `stripe` | Required for provider readiness; checkout/charging must still stay behind explicit product flow. |

## Support Contact Process

1. Assign one internal owner for each pilot user or company.
2. Use one shared support channel for routine issues.
3. Use direct escalation for safety, source-trust, export, privacy, or engineer-responsibility issues.
4. Acknowledge urgent issues the same business day.
5. Tell users to stop relying on affected output when the issue may involve stale, missing, unsupported, or unreviewed evidence.
6. Record every issue with owner, severity, project ID, reproduction status, and next action.

Severity guide:

| Severity | Use when | Response |
| --- | --- | --- |
| P0 | Safety, source trust, incorrect responsibility boundary, data exposure, or users could rely on invalid output | Disable affected access or feature path, notify pilot owner, begin rollback/disable plan |
| P1 | User blocked from key pilot workflow or exports/reports are misleading | Same-day triage and workaround |
| P2 | Workflow friction, confusing copy, recoverable bug, or non-critical visual issue | Track and batch |
| P3 | Nice-to-have feedback | Add to backlog |

## Bug Report Template

```text
Title:
Reporter:
Company/team:
Project name or ID:
Date/time with timezone:
Environment: local / staging / pilot deployment
Browser/device/OS:

What were you trying to do?

Steps to reproduce:
1.
2.
3.

Expected result:

Actual result:

Visible status/error text:

Files or inputs involved:

Did this involve address lookup, GIS/imagery candidates, drawn geometry, generated systems, exports, or review status?

Screenshots or recording:

Can the affected output be relied on? No / Unknown / User paused

Internal owner:
Severity:
Next action:
```

## Known Limitations

- Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.
- Construction release remains outside Civora.
- Exports are review packages unless externally approved by a licensed engineer outside Civora.
- Address lookup does not automatically create trusted site objects unless source-backed and accepted.
- GIS and imagery detections are candidates that require review.
- Civil3D workflows are not externally verified.
- DWG export is unsupported.
- Standards require user/company acceptance before they can be used as review evidence.
- Survey/control, datum, benchmark, and source evidence are required for production-grade review.
- Auth, SQLite storage, and in-process jobs are private-pilot grade, not broad production infrastructure.

## What Users Should Test

- Account creation and sign-in.
- Project creation, save, reopen, and history review.
- Address or blank-site start flow.
- Site boundary setup and lock behavior.
- Uploading approved test images, survey CSV files, and supported source files.
- Placing and editing site objects for concept review.
- Generating review-only grading, drainage, sanitary, water, utility, quantity, and export-package outputs.
- Reviewing assumptions, missing inputs, blockers, stale-output warnings, and low-confidence areas.
- Exporting engineer-review packages and confirming review-required language is visible.
- Reporting bugs with enough reproduction detail.

## What Users Should Not Rely On

- Civora output as stamped, sealed, signed, certified, submitted, approved, or construction-released work.
- Address lookup alone as survey, control, boundary, title, easement, right-of-way, utility, or standards evidence.
- GIS/imagery candidates without user or engineer review.
- Inferred standards, dimensions, or assumptions without accepted source evidence.
- Review exports as construction documents unless externally approved outside Civora.
- Any output that is marked blocked, missing input, stale, draft/review-required, visual preview only, or needs review.

## Engineer Responsibility Boundary

Civora can prepare candidate plans, calculations, assumptions, blockers, status summaries, and engineer-review packages. Civora cannot make professional approval decisions or carry legal responsibility.

The licensed engineer or user remains responsible for:

- source verification
- professional judgment
- jurisdictional and client requirements
- calculation and geometry review
- approval, stamping, sealing, signing, submission, and construction release outside Civora

## Rollback Or Disable Plan

Use this plan for P0 or high-risk P1 issues:

1. Pause new pilot invites.
2. Notify active affected users and tell them whether to stop using affected outputs.
3. Disable access by removing pilot users, rotating credentials, or taking the deployment offline if needed.
4. If the issue is frontend-only, roll back the Vercel deployment to the last known good build.
5. If the issue is backend-only, roll back the Railway deployment or stop the service.
6. Preserve logs, project IDs, report artifacts, and reproduction steps before cleanup.
7. Confirm env vars still point to the intended backend/frontend after rollback.
8. Re-run health, auth, project save/load, planner run, preview, and export sanity checks before re-enabling.
9. Document the incident, resolution, user impact, and follow-up owner.

## Daily Monitoring Checklist

Run this at the start and end of each pilot day:

- Check `/api/health`.
- Check `/api/auth/status`.
- Confirm frontend can reach `NEXT_PUBLIC_API_BASE_URL`.
- Confirm new login still works.
- Confirm project save/load works.
- Confirm queued or background jobs are not stuck.
- Confirm uploads and artifacts are stored under persistent storage.
- Confirm preview and review export still work.
- Review failed jobs, stale jobs, memory/runtime warnings, and queue length.
- Review support channel for unresolved issues.
- Review whether any user saw confusing responsibility, approval, or construction-release language.
- Confirm no temporary local CORS env vars remain enabled after QA sessions.

## Logs And Reports To Review After Each Pilot Day

- Backend runtime logs for errors, tracebacks, restarts, memory pressure, queue stalls, and failed jobs.
- Frontend deployment logs for build/runtime errors.
- Auth events for failed login spikes or unexpected access.
- Project save/load records for persistence failures.
- Upload and artifact records for missing files or broken paths.
- Export/report generation records for blocked or stale packages.
- `reports/alpha/alpha_smoke_soak_report_*.json` when generated.
- `reports/alpha/private_alpha_backend_readiness_report.json` when refreshed.
- Any daily support issues, screenshots, reproduction notes, and user-impact summaries.

## Remaining Pilot Ops Gaps To Track

- Final pilot roster owner and storage location.
- Final invite email/template and pilot terms link.
- Named support channel and after-hours escalation owner.
- Hosted pilot monitoring cadence and owner.
- Rollback owner for Vercel and Railway.
- Decision on whether pilot users may use confidential project inputs.
- Final data retention and deletion policy for pilot uploads and artifacts.
- Final confidential input approval policy.
- Final usage limits and charging rules.
- Counsel-approved pilot terms, privacy language, and billing language.
- Daily report archive location and naming convention.
