FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV GDAL_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_backend.txt .
RUN pip install -r requirements_backend.txt

COPY . .

ENV PERFORMANCE_AI_STORAGE_DIR=/data
ENV MPLCONFIGDIR=/tmp/mplconfig

EXPOSE 8002

CMD ["sh", "-c", "mkdir -p \"$PERFORMANCE_AI_STORAGE_DIR\" \"$MPLCONFIGDIR\" && if [ \"${CIVORA_PROCESS_ROLE:-combined}\" = \"worker\" ]; then exec python -m backend.scripts.run_job_worker; else exec gunicorn backend.api.app:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8002} --workers ${WEB_CONCURRENCY:-2} --timeout ${WEB_TIMEOUT_SECONDS:-35} --graceful-timeout 10 --keep-alive 3 --max-requests ${WEB_MAX_REQUESTS:-12} --max-requests-jitter 4 --access-logfile /dev/null --error-logfile - --log-level warning; fi"]
