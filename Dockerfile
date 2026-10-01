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
RUN pip install --upgrade pip "setuptools>=83.0.0" \
    && pip install -r requirements_backend.txt

COPY . .

ENV PERFORMANCE_AI_STORAGE_DIR=/data
ENV MPLCONFIGDIR=/tmp/mplconfig

RUN groupadd --gid 10001 civora \
    && useradd --uid 10001 --gid civora --no-create-home --shell /usr/sbin/nologin civora \
    && mkdir -p /data /tmp/mplconfig \
    && chown civora:civora /data /tmp/mplconfig

USER 10001:10001

EXPOSE 8002

CMD ["sh", "scripts/start_backend_service.sh"]
