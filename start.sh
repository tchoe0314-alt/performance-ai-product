#!/usr/bin/env bash


ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR"
FRONTEND_DIR="$ROOT_DIR/apps/web"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
UVICORN_RELOAD="${UVICORN_RELOAD:-0}"
MPL_CACHE_DIR="$ROOT_DIR/.mpl-cache"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "${FRONTEND_PID}" ]]; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-45}"
  local delay="${4:-1}"

  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi

  for ((i = 1; i <= attempts; i++)); do
    if curl --silent --fail "$url" >/dev/null 2>&1; then
      echo "$label is live: $url"
      return 0
    fi
    sleep "$delay"
  done

  echo "$label did not become ready: $url"
  return 1
}

ensure_backend_env() {
  require_cmd python3
  mkdir -p "$MPL_CACHE_DIR"

  if [[ ! -x "$PYTHON_BIN" || ! -x "$PIP_BIN" ]]; then
    if [[ -d "$VENV_DIR" ]]; then
      echo "Existing virtual environment looks incomplete. Rebuilding it..."
      rm -rf "$VENV_DIR"
    else
      echo "Creating Python virtual environment..."
    fi
    python3 -m venv "$VENV_DIR"
  fi

  if ! "$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "Installing backend dependencies..."
    "$PIP_BIN" install -r "$ROOT_DIR/requirements_backend.txt"
  fi

  if ! "$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "Backend dependencies are still missing after install."
    echo "Try running: $PIP_BIN install -r $ROOT_DIR/requirements_backend.txt"
    exit 1
  fi
}

ensure_frontend_env() {
  if [[ ! -d "$FRONTEND_DIR" ]]; then
    return 1
  fi

  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Node/npm not found. Skipping frontend startup."
    return 1
  fi

  if [[ ! -f "$FRONTEND_DIR/.env.local" && -f "$FRONTEND_DIR/.env.example" ]]; then
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
  fi

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
  fi

  return 0
}

start_backend() {
  echo "Starting backend on http://127.0.0.1:8002 ..."
  (
    cd "$BACKEND_DIR"
    export MPLCONFIGDIR="$MPL_CACHE_DIR"
    if [[ "$UVICORN_RELOAD" == "1" ]]; then
      exec "$PYTHON_BIN" -m uvicorn backend.api.app:app --reload --port 8002
    fi
    exec "$PYTHON_BIN" -m uvicorn backend.api.app:app --port 8002
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  echo "Starting frontend on http://localhost:3000 ..."
  (
    cd "$FRONTEND_DIR"
    exec npm run dev
  ) &
  FRONTEND_PID=$!
}

main() {
  echo "Booting Performance AI from $ROOT_DIR"

  ensure_backend_env
  start_backend

  if ! wait_for_url "http://127.0.0.1:8002/api/health" "Backend"; then
    echo "Backend failed to start cleanly."
    exit 1
  fi

  if ensure_frontend_env; then
    start_frontend
    if ! wait_for_url "http://127.0.0.1:3000" "Frontend"; then
      echo "Frontend did not start. Check the npm output above."
    fi
  fi

  echo
  echo "Performance AI is starting."
  echo "Backend:  http://127.0.0.1:8002/api/health"
  if [[ -n "${FRONTEND_PID}" ]]; then
    echo "Frontend: http://localhost:3000"
  fi
  echo
  echo "Press Ctrl+C to stop everything."

  wait
}

main "$@"
