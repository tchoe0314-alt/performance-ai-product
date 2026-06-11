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
CIVORA_AI_PROVIDER=openai
OPENAI_API_KEY=your_real_key
PERFORMANCE_AI_STORAGE_DIR=/data
CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app,https://civoraai.com,https://www.civoraai.com
MAPBOX_TOKEN=your_backend_mapbox_token
```

For a deployment that avoids paid language calls, set `CIVORA_AI_PROVIDER=none`.
For a self-hosted local model worker, set `CIVORA_AI_PROVIDER=ollama` and configure `CIVORA_OLLAMA_BASE_URL`.
If `MAPBOX_TOKEN` is missing or rejected, `/api/geocode` should return a structured blocked response instead of `500`; address lookup remains review context only and is not survey, boundary, or control evidence.

Do not set `CORS_ALLOW_ORIGINS=*` for private alpha or production. The backend only permits wildcard CORS in local/development mode.

For a temporary pilot QA session where a local frontend must call the live backend, set both variables explicitly on the backend:

```bash
CIVORA_ALLOW_LOCAL_PILOT_CORS=true
CIVORA_LOCAL_PILOT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Remove `CIVORA_ALLOW_LOCAL_PILOT_CORS` after the QA session. Local frontend to local backend does not need the live API CORS exception.

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

The validator blocks missing required production config, invalid public URLs, wildcard CORS outside local/development, provider mismatches, Railway healthcheck mismatch, and Vercel API-base mistakes. It prints redacted diagnostics only.

Backend:

- health works at `/api/health`
- Railway `healthcheckPath` is `/api/health`; do not point it at a frontend route or a placeholder path
- auth status works at `/api/auth/status`
- uploads succeed
- preview/export succeed
- project save/load works

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
- auth is still beta-grade app auth
- SQLite is fine for a small beta, but not ideal for bigger multi-user scale
- in-process jobs are fine for a small beta, but not for heavier production load
- API success means the service responded; Civora output remains review-only and does not replace licensed engineering judgment or project source control.

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
