#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
export CIVORA_GATEWAY_DETECTOR_KIND="${CIVORA_GATEWAY_DETECTOR_KIND:-civora}"
export CIVORA_GATEWAY_MAPBOX_STYLE="${CIVORA_GATEWAY_MAPBOX_STYLE:-mapbox/satellite-v9}"
export CIVORA_GATEWAY_IMAGE_SIZE="${CIVORA_GATEWAY_IMAGE_SIZE:-1024x1024}"
export CIVORA_GATEWAY_CIVORA_MAX_SIZE="${CIVORA_GATEWAY_CIVORA_MAX_SIZE:-768}"

exec python3 -m uvicorn backend.scripts.imagery_detection_gateway:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8090}"
