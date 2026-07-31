# Production Env Validator V1

`production_env_validator_v1` blocks Vercel/Railway releases when required production configuration is missing, malformed, or unsafe. It emits redacted diagnostics only: secret values are reported as present/length metadata, never as raw values.

Run locally or in deploy checks:

```bash
python scripts/production_env_validator_v1.py --target railway
python scripts/production_env_validator_v1.py --target vercel
```

Use `--warn-only` for discovery runs that should not fail the shell command.

## Required Env Vars

Required for `private_alpha`, `public_beta`, or `production` as noted by the validator output:

- `CIVORA_PRODUCT_MODE`
- `NEXT_PUBLIC_API_BASE_URL` for `public_beta` and `production`
- `CIVORA_PUBLIC_API_BASE_URL` for `public_beta` and `production`
- `CORS_ALLOW_ORIGINS`
- `CIVORA_SESSION_SECRET` for `public_beta` and `production`
- `PERFORMANCE_AI_STORAGE_DIR`
- `CIVORA_AI_PROVIDER` for `public_beta` and `production`

Provider-conditional blockers:

- `OPENAI_API_KEY` when `CIVORA_AI_PROVIDER=openai`
- `CIVORA_OLLAMA_BASE_URL` when `CIVORA_AI_PROVIDER=ollama` or `local`
- Stripe keys when `CIVORA_BILLING_PROVIDER=stripe`
- `CIVORA_GIS_PROVIDER_REGISTRY_URL` when `CIVORA_REQUIRE_GIS_PROVIDERS=true`

Public beta/production operational blockers:

- `CIVORA_SUPPORT_CONTACT_URL` or `CIVORA_SUPPORT_EMAIL`
- `CIVORA_BUG_REPORT_URL`
- `CIVORA_ESCALATION_CONTACT`
- `CIVORA_MONITORING_OWNER`
- `CIVORA_ROLLBACK_OWNER`
- `CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN=true`

## Optional Env Vars

- `DATABASE_URL`
- `CIVORA_FRONTEND_PUBLIC_URL`
- `MAPBOX_TOKEN`
- `NEXT_PUBLIC_MAPBOX_TOKEN`
- `CIVORA_CRON_SECRET`
- `CIVORA_JOB_TIMEOUT_SECONDS`
- `CIVORA_MEMORY_WARN_MB`
- `CIVORA_RUNTIME_DEBUG_BEARER_TOKEN`
- `CIVORA_MAX_IMAGE_UPLOAD_BYTES`
- `CIVORA_MAX_SURVEY_UPLOAD_BYTES`
- `CIVORA_MAX_EXISTING_CONDITIONS_UPLOAD_BYTES`
- `CIVORA_SUPPORT_CONTACT_URL`
- `CIVORA_SUPPORT_EMAIL`
- `CIVORA_BUG_REPORT_URL`
- `CIVORA_ESCALATION_CONTACT`
- `CIVORA_MONITORING_OWNER`
- `CIVORA_ROLLBACK_OWNER`
- `CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN`
- `CIVORA_ALLOW_LOCAL_PILOT_CORS`
- `CIVORA_LOCAL_PILOT_CORS_ORIGINS`
- `CIVORA_BILLING_PROVIDER`
- `CIVORA_ENABLE_REAL_CHARGING`
- `CIVORA_BILLING_LEGAL_DOCS_READY`
- `CIVORA_OCR_ENGINE`
- `CIVORA_OCR_LANG`
- `CIVORA_PDF_RENDERER`
- `CIVORA_GIS_PROVIDER_REGISTRY_URL`
- `CIVORA_IMAGERY_DETECTION_PROVIDER`
- `CIVORA_IMAGERY_DETECTION_URL`
- `CIVORA_IMAGERY_DETECTION_TOKEN`

Missing optional providers become warnings by default. They become blockers when the selected mode or explicit requirement flag makes them necessary.

## Platform Checks

Vercel:

- project root should be `apps/web`
- `NEXT_PUBLIC_API_BASE_URL` must be an absolute backend URL
- `CIVORA_FRONTEND_PUBLIC_URL` or `VERCEL_URL` is checked against `CORS_ALLOW_ORIGINS` when present
- localhost API URLs block `public_beta` and `production`
- temporary local-to-live backend CORS is reported as a warning in `public_beta` and `production`

Railway:

- backend must bind to `${PORT:-8002}`
- healthcheck path must be `/api/health`
- public backend URL must be absolute when supplied
- persistent storage should be an absolute mounted path
- upload limits should be explicit when pilot operators need a known support boundary

## Safe Debug Endpoint

Authenticated users can call:

```text
GET /api/debug/production-env
```

The endpoint returns the same redacted report and is rate-limited with the existing debug bucket. It does not return secret values and it does not change billing, provider, or access settings.

## Public Beta Reading

`status=ready` only means this env contract is satisfied. It does not mean Civora is construction ready. Public beta remains blocked unless support owner, bug intake, privacy/terms, data retention, production storage and queue decisions, billing/legal gates, deployment rollback owner, monitoring cadence, review-only responsibility language, and `CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN=true` are all accepted by the owner.
