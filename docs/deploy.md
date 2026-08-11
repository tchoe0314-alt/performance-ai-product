# Deploy Civora AI

This repo is easiest to deploy as:

- frontend on Vercel
- backend on Railway

That fits the current product shape well:

- `apps/web` is a standalone Next.js app
- the backend is a FastAPI service
- the backend currently uses SQLite plus local uploads/artifacts, so it needs persistent storage

## Recommended setup

### 1. Deploy the backend to Railway

Use the repo root as the Railway service source so Railway can build the root [Dockerfile](/Users/tommychoe/Documents/Playground/Civora%20AI/Dockerfile).

Set these Railway variables:

```bash
CIVORA_PRODUCT_MODE=private_alpha
CIVORA_DEPLOYMENT_TARGET=railway
CIVORA_PUBLIC_API_BASE_URL=https://your-backend-domain.up.railway.app
CIVORA_AI_PROVIDER=openai
OPENAI_API_KEY=your_real_key
PERFORMANCE_AI_STORAGE_DIR=/data
CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app,https://civoraai.com,https://www.civoraai.com
MAPBOX_TOKEN=your_backend_mapbox_token
CIVORA_IMAGERY_DETECTION_PROVIDER=your_detector_name
CIVORA_IMAGERY_DETECTION_URL=https://your-detector.example.com/detect
CIVORA_IMAGERY_DETECTION_TOKEN=your_detector_bearer_token
CIVORA_MAX_IMAGE_UPLOAD_BYTES=10485760
CIVORA_MAX_SURVEY_UPLOAD_BYTES=5242880
CIVORA_MAX_EXISTING_CONDITIONS_UPLOAD_BYTES=26214400
CIVORA_SUPPORT_CONTACT_URL=https://your-support-page.example
CIVORA_BUG_REPORT_URL=https://your-bug-intake-form.example
CIVORA_ESCALATION_CONTACT=ops-owner@example.com
CIVORA_MONITORING_OWNER=ops-owner@example.com
CIVORA_ROLLBACK_OWNER=release-owner@example.com
CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN=false
```

For hosted environments, run long work outside the request-serving API:

```text
# API service
CIVORA_PROCESS_ROLE=combined
CIVORA_DEDICATED_WORKER_ENABLED=true
CIVORA_DISABLED_JOB_TYPES=source_context
PERFORMANCE_AI_JOB_WORKERS=1
DATABASE_URL=<shared Railway Postgres URL>
CIVORA_DATABASE_POOL_MIN_SIZE=1
CIVORA_DATABASE_POOL_MAX_SIZE=4

# Worker service built from the same Dockerfile/revision
CIVORA_PROCESS_ROLE=worker
CIVORA_ENABLED_JOB_TYPES=source_context
PERFORMANCE_AI_JOB_WORKERS=1
DATABASE_URL=<the same shared Railway Postgres URL>
CIVORA_DATABASE_POOL_MIN_SIZE=1
CIVORA_DATABASE_POOL_MAX_SIZE=2
PERFORMANCE_AI_RESUME_PENDING_JOBS=true
PERFORMANCE_AI_RESUME_POLL_SECONDS=1
```

If the API is intentionally deployed as `CIVORA_PROCESS_ROLE=web`, set
`CIVORA_EXTERNAL_WORKER_CONFIRMED=true` only after the separate worker has
successfully completed a queued hosted job on the same Postgres database, and
set `CIVORA_EXTERNAL_WORKER_HEALTH_URL` to its HTTPS `/api/health` endpoint.
Web startup verifies that the endpoint reports a live worker with the
`source_context` handler. When that proof is missing or unhealthy, startup
automatically uses the process-isolated combined supervisor so queued work
cannot remain stranded.

The services must use the same production database. Each sibling process uses a bounded Postgres connection pool: six web connections and two worker connections by default, with eight bounded web request threads. Override them with `CIVORA_WEB_DATABASE_POOL_MAX_SIZE`, `CIVORA_WORKER_DATABASE_POOL_MAX_SIZE`, and `CIVORA_ANYIO_THREAD_LIMIT` only after checking the hosted database connection limit. When `combined` mode detects Postgres, the container automatically supervises a request-only API process plus an isolated worker for every queued job type. The worker runs at niceness 10 by default so interactive API traffic keeps CPU priority on a shared Railway container; `CIVORA_WORKER_NICE_LEVEL` can override the value from 0 through 19. Both sibling processes share the same mounted files, so PDF analysis and artifact exports stay available without running numerical work in the request process. Set `CIVORA_COMBINED_PROCESS_ISOLATION=false` only for diagnosis. A separately deployed `worker` service remains supported. It exposes a minimal `/api/health` endpoint on `PORT` so Railway can verify it without exposing job payloads or user data.


For a deployment that avoids paid language calls, set `CIVORA_AI_PROVIDER=none`.
For a self-hosted local model worker, set `CIVORA_AI_PROVIDER=ollama` and configure `CIVORA_OLLAMA_BASE_URL`.
If `MAPBOX_TOKEN` is missing or rejected, `/api/geocode` should return a structured blocked response instead of `500`; address lookup remains review context only and is not survey, boundary, or control evidence.

If `CIVORA_IMAGERY_DETECTION_URL` is configured, Apply Address also sends the address/geocode, search bbox, active site boundary, and requested candidate types to that endpoint. The detector should return JSON like:

```json
{
  "status": "detected",
  "provider": "aerial-object-detector",
  "source_url": "https://imagery-source.example/tile-or-scene",
  "detections": [
    {
      "kind": "building",
      "geometry": { "type": "Polygon", "coordinates": [] },
      "confidence": 0.82
    }
  ]
}
```

Supported `kind` values include `building`, `road`, `driveway`, `parking`, `sidewalk`, `tree`, `vegetation`, `basin`, `pond`, `utility`, `inlet`, `outfall`, `manhole`, and `hydrant`. These detections become visual review candidates only. If this provider is missing, Apply Address still uses GIS/provider candidates and uploaded map/image detection, but it must not invent buildings from an address alone.

The repo includes a deployable gateway at `backend/scripts/imagery_detection_gateway.py` for providers that need a source image instead of an address/bbox. Run it as a separate service and point `CIVORA_IMAGERY_DETECTION_URL` at `/detect`.

Built-in Civora detector gateway:

```bash
python3 -m uvicorn backend.scripts.imagery_detection_gateway:app --host 0.0.0.0 --port 8090
```

```bash
CIVORA_GATEWAY_DETECTOR_KIND=civora
CIVORA_GATEWAY_MAPBOX_TOKEN=your_mapbox_token
CIVORA_GATEWAY_MAPBOX_STYLE=mapbox/satellite-v9
CIVORA_GATEWAY_IMAGE_SIZE=1024x1024
CIVORA_GATEWAY_CIVORA_MAX_SIZE=768
```

This mode downloads the source image and runs Civora's built-in heuristic detector. It is useful immediately for visual candidate extraction and QA demos, but it is still approximate. Use it as a baseline while collecting labeled aerial/site-plan examples for a trained model.

Generic detector gateway:

```bash
python3 -m uvicorn backend.scripts.imagery_detection_gateway:app --host 0.0.0.0 --port 8090
```

```bash
CIVORA_GATEWAY_DETECTOR_KIND=generic
CIVORA_GATEWAY_MAPBOX_TOKEN=your_mapbox_token
CIVORA_GATEWAY_MAPBOX_STYLE=mapbox/satellite-v9
CIVORA_GATEWAY_IMAGE_SIZE=1024x1024
CIVORA_GATEWAY_GENERIC_DETECTOR_URL=https://your-detector.example.com/detect
CIVORA_GATEWAY_GENERIC_DETECTOR_TOKEN=your_detector_token
```

Roboflow-style gateway:

```bash
CIVORA_GATEWAY_DETECTOR_KIND=roboflow
CIVORA_GATEWAY_MAPBOX_TOKEN=your_mapbox_token
ROBOFLOW_API_URL=https://serverless.roboflow.com/your-model/your-version
ROBOFLOW_API_KEY=your_roboflow_key
ROBOFLOW_IMAGE_MODE=url_param
```

The gateway creates a static imagery URL from the active bbox/site boundary, calls the configured detector, normalizes labels such as building roof, road, parking, tree canopy, basin/pond, inlet/outfall/manhole/hydrant, and returns Civora-compatible visual candidates. Confirm Mapbox/imagery/detector terms allow this use before enabling it for real projects.

Do not set `CORS_ALLOW_ORIGINS=*` for private alpha or production. The backend only permits wildcard CORS in local/development mode.

For a temporary pilot QA session where a local frontend must call the live backend, set both variables explicitly on the backend:

```bash
CIVORA_ALLOW_LOCAL_PILOT_CORS=true
CIVORA_LOCAL_PILOT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Remove `CIVORA_ALLOW_LOCAL_PILOT_CORS` after the QA session. Local frontend to local backend does not need the live API CORS exception.
For public beta or production, the validator warns while temporary local CORS is enabled so it is not forgotten after live QA.

Attach a persistent Railway volume and mount it at:

```text
/data
```

Why:

- SQLite database lives inside `PERFORMANCE_AI_STORAGE_DIR`
- uploaded images live there too
- generated artifacts live there too

Once deployed, note the public backend URL, for example:

```text
https://civora-ai-backend.up.railway.app
```

### 2. Deploy the frontend to Vercel

Create a Vercel project from this same repo, but set the root directory to:

```text
apps/web
```

Add this environment variable in Vercel:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain.up.railway.app
CIVORA_FRONTEND_PUBLIC_URL=https://your-frontend-domain.vercel.app
```

For local frontend development against the local backend, use:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8002
```

Then deploy.

## Minimal production checklist

Run the environment validator before deploy:

```bash
python scripts/production_env_validator_v1.py --target railway
python scripts/production_env_validator_v1.py --target vercel
```

The validator blocks missing required production config, invalid public URLs, wildcard CORS outside local/development, provider mismatches, Railway healthcheck mismatch, Vercel API-base mistakes, and public beta/production without support, bug intake, monitoring owner, rollback owner, and an explicit `CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN=true` owner gate. It prints redacted diagnostics only.

Backend:

- health works at `/api/health`
- deployment health shows frontend, backend, API URL, auth, queue, build, and deploy metadata without secrets
- deployment health shows support and bug-report availability without secrets
- Railway `healthcheckPath` is `/api/health`; do not point it at a frontend route or a placeholder path
- auth status works at `/api/auth/status`
- uploads fail clearly for unsupported file types or size limits
- production env validator works at authenticated `GET /api/debug/production-env` and returns redacted diagnostics only
- preview/export succeed
- project save/load works
- billing status shows disabled, blocked, or enabled and never charges without explicit billing/legal/provider flags

Frontend:

- Vercel project root directory is `apps/web`; the repo root has no frontend `package.json`
- `NEXT_PUBLIC_API_BASE_URL` points at the live Railway backend URL and must not be a localhost URL in Vercel
- login works
- project save works
- planner run works
- preview works
- DXF/report download works

## Deployment crash triage

Vercel build failures usually mean the production build did not run from `apps/web` or TypeScript failed during `npm run build`.
Verify with:

```bash
cd apps/web
npm ci
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

Railway runtime failures usually come from backend startup, env, storage, or healthcheck configuration.
Verify with:

```bash
python -m py_compile backend/api/app.py
python -c "import backend.api.app as app; print(any(getattr(route, 'path', '') == '/api/health' for route in app.app.routes))"
uvicorn backend.api.app:app --host 127.0.0.1 --port 8002
curl --fail http://127.0.0.1:8002/api/health
```

If Railway has an attached persistent volume from an older build, startup must migrate the existing SQLite schema before creating indexes that depend on newer columns. Do not delete the volume as a first response; fix the migration or back up the data before repair.

## Important current limits

- this is a strong private beta deployment, not a full production platform yet
- public beta remains blocked until owner-approved support, privacy, billing/legal, production storage/queue, monitoring, and release gates are complete
- `CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN=false` is the default and must stay false until all gates are externally accepted by the owner
- auth is still beta-grade app auth
- SQLite is fine for a small beta, but not ideal for bigger multi-user scale
- in-process jobs are fine for a small beta, but not for heavier production load
- API success means the service responded; Civora output remains review-only and does not replace licensed engineering judgment or project source control.

## Disable Or Roll Back

Use this process for P0/P1 access, source-trust, billing, upload, auth, or deployment-health incidents:

1. Pause new invites and tell affected users whether to stop relying on affected outputs.
2. Disable the risky path first: remove pilot users, rotate credentials, set `CIVORA_ENABLE_PUBLIC_ACCESS=false`, set `CIVORA_PAID_PILOT_MODE=false`, set `CIVORA_ENABLE_REAL_CHARGING=false`, or stop the backend service as needed.
3. Roll back Vercel for frontend-only incidents.
4. Roll back or stop Railway for backend/API/auth/upload/job incidents.
5. Preserve project IDs, logs, artifacts, screenshots, env-validator reports, and reproduction steps.
6. Re-run health, auth, billing status, upload, project save/load, planner run, preview, and export checks before re-enabling.

## Fast local sanity check before deploy

```bash
cd "/Users/tommychoe/Documents/Playground/Civora AI"
./start.sh
```

Frontend local:

```text
http://localhost:3000
```

Backend local:

```text
http://127.0.0.1:8002/api/health
```
