# Performance AI

Performance AI is an AI-assisted civil site planning product. The codebase combines:

- a Next.js frontend for prompt, image, and structured project intake
- a FastAPI backend for orchestration and uploads
- Python planning engines for civil layout, grading, drainage, and utility workflows

## Current structure

```text
performance-ai-product/
  apps/
    web/                  # Main Next.js product UI
      lib/                # Frontend API helpers
  backend/
    api/                  # Product API package
    planning/             # Product-facing planner package wrappers
  archive/
    next-starter/         # Original unused Next starter app
  backend_api_main.py     # FastAPI entrypoint
  planner_orchestrator.py # Main orchestration shell
  planner.py              # Core planning engine
  planner_intelligence.py # Candidate scoring and refinement
  core/                   # Shared planning logic
  engines/                # Discipline-specific engines
  parsers/                # Prompt/sketch parsers
  vision/                 # Image analysis
  docs/                   # Product docs
```

## What to keep using

- Frontend: `apps/web`
- Backend entrypoint: `backend_api_main.py`
- Main orchestration logic: `planner_orchestrator.py`

## Local run

### One command

```bash
cd /Users/tommychoe/Documents/Playground/performance-ai-product
./start.sh
```

The script will:

- create `.venv` if needed
- install backend dependencies if missing
- copy `apps/web/.env.example` to `apps/web/.env.local` if needed
- install frontend dependencies if `node`/`npm` are available
- start the backend and frontend together

If `node` or `npm` is missing, it will still start the backend and skip the frontend.

### Frontend

```bash
cd /Users/tommychoe/Documents/Playground/performance-ai-product/apps/web
npm install
npm run dev
```

### Backend

```bash
cd /Users/tommychoe/Documents/Playground/performance-ai-product
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_backend.txt
uvicorn backend.api.app:app --reload --port 8002
```

## Architecture notes

- `backend.api.app` is now the preferred FastAPI entrypoint.
- `backend.planning.*` is the preferred product namespace for planner access.
- `backend.services.auth_store` provides local beta auth with bearer tokens.
- `backend.services.project_store` provides SQLite-backed user-scoped project save/load.
- `backend.services.job_queue` provides SQLite-backed background orchestration jobs with status tracking.
- the frontend now includes a dashboard flow for register/login, saved projects, queued jobs, and planner result review
- The large root planner/core/engine files are still the source of truth for now.
- `backend_api_main.py` remains as a compatibility wrapper so older commands do not break.

## Beta flow

1. Run `./start.sh`
2. Open `http://localhost:3000`
3. Create a beta account on the auth screen
4. Build a request, save it as a project, or queue a planner job
5. Review assumptions, issues, and backend result output in the dashboard

## Current beta limits

- Auth is local to this app instance and is not yet production-grade identity.
- Storage is SQLite and the job worker runs in-process, which is fine for a private beta but not a multi-instance deployment.
- Prompt-based orchestration still requires a valid `OPENAI_API_KEY` in your backend environment.
- Frontend build verification still depends on having `node` and `npm` installed on the machine running the app.

## Product direction

The strongest near-term product shape is:

1. Intake: prompt, image, and structured site fields
2. Orchestration: infer blanks, validate assumptions, and build candidate plans
3. Review: show assumptions, issues, and option tradeoffs
4. Export: package outputs such as reports and DXF artifacts

More detail lives in `docs/product-foundation.md`.
