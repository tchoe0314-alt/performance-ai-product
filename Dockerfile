FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

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

CMD ["sh", "-c", "mkdir -p \"$PERFORMANCE_AI_STORAGE_DIR\" \"$MPLCONFIGDIR\" && uvicorn backend.api.app:app --host 0.0.0.0 --port ${PORT:-8002}"]
