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
  external_worker_health_url="${CIVORA_EXTERNAL_WORKER_HEALTH_URL:-}"
  external_worker_is_live="false"
  if { [ "$external_worker_confirmed" = "1" ] || [ "$external_worker_confirmed" = "true" ]; } && [ -n "$external_worker_health_url" ]; then
    if python - "$external_worker_health_url" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

request = Request(sys.argv[1], headers={"Accept": "application/json"})
with urlopen(request, timeout=5) as response:  # nosec B310 - operator-configured deployment health URL
    payload = json.load(response)

handlers = {str(item) for item in payload.get("registered_handlers") or []}
if (
    str(payload.get("service") or "") != "civora-job-worker"
    or int(payload.get("alive_workers") or 0) < 1
    or "source_context" not in handlers
):
    raise SystemExit(1)
PY
    then
      external_worker_is_live="true"
    fi
  fi
  if [ -n "${DATABASE_URL:-}" ] && [ "$external_worker_is_live" != "true" ]; then
    # A web-only deployment must not silently strand queued work. Until an
    # external worker is both configured and live, supervise an isolated
    # low-priority worker beside the request process.
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
