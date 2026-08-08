#!/usr/bin/env sh

set -eu

mkdir -p "${PERFORMANCE_AI_STORAGE_DIR:-/data}" "${MPLCONFIGDIR:-/tmp/mplconfig}"

role="${CIVORA_PROCESS_ROLE:-combined}"
port="${PORT:-8002}"
timeout="${WEB_TIMEOUT_SECONDS:-35}"

if [ "$role" = "worker" ]; then
  exec python -m backend.scripts.run_job_worker
fi

if [ "$role" = "web" ]; then
  external_worker_confirmed="${CIVORA_EXTERNAL_WORKER_CONFIRMED:-false}"
  if [ -n "${DATABASE_URL:-}" ] && [ "$external_worker_confirmed" != "1" ] && [ "$external_worker_confirmed" != "true" ]; then
    # A web-only deployment must not silently strand queued work. Until an
    # external worker is explicitly confirmed, supervise an isolated low-
    # priority worker beside the request process.
    exec python -m backend.scripts.run_combined_backend
  fi
  exec gunicorn backend.api.app:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind "0.0.0.0:${port}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout "$timeout" \
    --graceful-timeout 10 \
    --keep-alive 3 \
    --max-requests "${WEB_MAX_REQUESTS:-250}" \
    --max-requests-jitter "${WEB_MAX_REQUESTS_JITTER:-25}" \
    --access-logfile /dev/null \
    --error-logfile - \
    --log-level warning
fi

combined_process_isolation="${CIVORA_COMBINED_PROCESS_ISOLATION:-auto}"
if [ "$role" = "combined" ] && [ -n "${DATABASE_URL:-}" ] && [ "$combined_process_isolation" != "0" ] && [ "$combined_process_isolation" != "false" ]; then
  # Hosted Postgres deployments can safely share queued job state across
  # processes. Keep CPU-heavy orchestration out of the request process so
  # authentication, projects, and job controls remain responsive during runs.
  exec python -m backend.scripts.run_combined_backend
fi

# Combined mode owns in-process job threads. Keep exactly one stable Gunicorn
# process so request recycling or competing process-local queues cannot kill or
# duplicate a long-running engineering job.
exec gunicorn backend.api.app:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${port}" \
  --workers 1 \
  --timeout "$timeout" \
  --graceful-timeout 10 \
  --keep-alive 3 \
  --max-requests 0 \
  --max-requests-jitter 0 \
  --access-logfile /dev/null \
  --error-logfile - \
  --log-level warning
