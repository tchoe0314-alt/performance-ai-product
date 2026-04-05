FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV MPLCONFIGDIR=/opt/mplconfig

WORKDIR /app

RUN python -m venv "$VIRTUAL_ENV"

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_backend.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements_backend.txt
RUN mkdir -p "$MPLCONFIGDIR" \
    && python -c "import matplotlib; import matplotlib.font_manager; print('matplotlib cache warmed')"

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV MPLCONFIGDIR=/opt/mplconfig

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/mplconfig /opt/mplconfig
COPY . .

ENV PERFORMANCE_AI_STORAGE_DIR=/data
EXPOSE 8002

CMD ["sh", "-c", "mkdir -p \"$PERFORMANCE_AI_STORAGE_DIR\" \"$MPLCONFIGDIR\" && uvicorn backend.api.app:app --host 0.0.0.0 --port ${PORT:-8002}"]
