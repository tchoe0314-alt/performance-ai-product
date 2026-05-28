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
CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app
```

For a deployment that avoids paid language calls, set `CIVORA_AI_PROVIDER=none`.
For a self-hosted local model worker, set `CIVORA_AI_PROVIDER=ollama` and configure `CIVORA_OLLAMA_BASE_URL`.

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

Then deploy.

## Minimal production checklist

Backend:

- health works at `/api/health`
- auth status works at `/api/auth/status`
- uploads succeed
- preview/export succeed
- project save/load works

Frontend:

- login works
- project save works
- planner run works
- preview works
- DXF/report download works

## Important current limits

- this is a strong private beta deployment, not a full production platform yet
- auth is still beta-grade app auth
- SQLite is fine for a small beta, but not ideal for bigger multi-user scale
- in-process jobs are fine for a small beta, but not for heavier production load

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
