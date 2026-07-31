# Architecture

## Product flow

1. The web app in `apps/web` collects prompt, image, and structured project inputs.
2. The web app calls the FastAPI backend at `backend.api.app`.
3. The API builds a planner orchestrator request and hands it to the planning layer.
4. `planner_orchestrator.py` routes inputs and manages workflow decisions.
5. `planner.py` executes the actual design stages using shared `core` state and discipline `engines`.
6. Results return to the UI as assumptions, issues, metadata, and final plan content.
7. Saved projects, auth sessions, and queued jobs are persisted through `backend/services`.

## Current source-of-truth modules

- API entrypoint: `backend/api/app.py`
- Product services: `backend/services/`
- Orchestration shell: `planner_orchestrator.py`
- Execution planner: `planner.py`
- Intelligence/scoring: `planner_intelligence.py`
- Shared system state: `core/`
- Discipline logic: `engines/`

## Why the backend package exists

The repo originally grew from top-level Python files. The new `backend/` package gives the product a clean namespace without forcing a risky full move of the planner and engine modules in one pass.

That means:

- new product code should prefer `backend.api.*`
- new planner-facing imports should prefer `backend.planning.*`
- existing root imports still work while the codebase is being stabilized

## Beta backend shape

- `backend/services/database.py` owns the SQLite schema and connection setup
- `backend/services/auth_store.py` manages local beta users and bearer tokens
- `backend/services/project_store.py` stores user-scoped projects and latest planner results
- `backend/services/job_queue.py` persists queued jobs and can run them in-process or through a dedicated worker service
- `apps/web/app/page.tsx` is the current beta dashboard for auth, projects, jobs, review, and planner controls

## Hosted background work

Use separate web and worker services when source detection, GIS, PDF analysis, generation, or exports are enabled:

- Web service: `CIVORA_PROCESS_ROLE=web`, `CIVORA_DEDICATED_WORKER_ENABLED=true`, `PERFORMANCE_AI_JOB_WORKERS=0`
- Worker service: `CIVORA_PROCESS_ROLE=worker`, `PERFORMANCE_AI_JOB_WORKERS=1`, `PERFORMANCE_AI_RESUME_POLL_SECONDS=1`
- Both services must use the same Postgres `DATABASE_URL`; process-local SQLite cannot coordinate a hosted split queue.
- Both services must share the same production database and persistent storage configuration.

The web service accepts and polls jobs but does not execute heavy handlers. The worker service claims persisted jobs atomically, publishes progress, and saves results. `combined` remains the local-development default.
