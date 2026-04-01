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
- `backend/services/job_queue.py` persists queued jobs and runs them with an in-process worker
- `apps/web/app/page.tsx` is the current beta dashboard for auth, projects, jobs, review, and planner controls
