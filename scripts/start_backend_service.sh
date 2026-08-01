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
