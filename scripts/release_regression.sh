#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"
RELEASE_DIST_DIR="${NEXT_RELEASE_DIST_DIR:-.next}"
PLAYWRIGHT_SPECS=(
  "tests/live/ui-functionality-chat32.spec.ts"
  "tests/live/civil-3d-viewer.spec.ts"
)
BACKEND_SMOKE_TESTS=(
  "tests/test_release_gates.py"
  "tests/test_alpha_smoke_soak.py"
)

PASSED=()
FAILED=()
SKIPPED=()
SERVER_PID=""

record_pass() {
  PASSED+=("$1")
}

record_fail() {
  FAILED+=("$1: $2")
}

record_skip() {
  SKIPPED+=("$1: $2")
  printf '[skip] %s - %s\n' "$1" "$2"
}

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

run_step() {
  local name="$1"
  shift
  printf '\n[run] %s\n' "$name"
  "$@"
  local status=$?
  if [[ $status -eq 0 ]]; then
    record_pass "$name"
  else
    record_fail "$name" "exit $status"
  fi
  return "$status"
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

port_is_free() {
  local port="$1"
  python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(1)
PY
}

find_free_port() {
  python3 <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

wait_for_url() {
  local url="$1"
  python3 - "$url" <<'PY'
import sys
import time
from urllib.request import urlopen

url = sys.argv[1]
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with urlopen(url, timeout=2) as response:
            if 200 <= response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(1)
raise SystemExit(1)
PY
}

printf 'Civora release regression\n'
printf 'Root: %s\n' "$ROOT_DIR"
printf 'Frontend release distDir: %s\n' "$RELEASE_DIST_DIR"
printf 'Note: this command uses the frontend stable build wrapper so generated Next artifacts are cleaned and retried consistently.\n'

if [[ ! -d "$WEB_DIR" ]]; then
  record_skip "frontend build/lint/playwright" "apps/web is missing"
else
  if ! has_command node || ! has_command npm; then
    record_skip "frontend build" "node and npm are required"
    record_skip "frontend lint" "node and npm are required"
    record_skip "selected Playwright" "node and npm are required"
  elif [[ ! -d "$WEB_DIR/node_modules" ]]; then
    record_skip "frontend build" "apps/web/node_modules is missing; run npm install in apps/web"
    record_skip "frontend lint" "apps/web/node_modules is missing; run npm install in apps/web"
    record_skip "selected Playwright" "apps/web/node_modules is missing; run npm install in apps/web"
  else
    (
      cd "$WEB_DIR" &&
        NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=8192}" \
        NEXT_PRODUCTION_BROWSER_SOURCE_MAPS=0 \
        npm run build
    )
    build_status=$?
    if [[ $build_status -eq 0 ]]; then
      record_pass "frontend build"
    else
      record_fail "frontend build" "exit $build_status"
    fi

    run_step "frontend lint" bash -c "cd \"\$1\" && npm run lint" bash "$WEB_DIR"

    if [[ $build_status -ne 0 ]]; then
      record_skip "selected Playwright" "frontend release build failed"
    elif ! has_command python3; then
      record_skip "selected Playwright" "python3 is required to allocate and probe a local port"
    else
      PORT="${RELEASE_REGRESSION_PORT:-}"
      if [[ -n "$PORT" ]]; then
        if ! port_is_free "$PORT"; then
          record_skip "selected Playwright" "RELEASE_REGRESSION_PORT=$PORT is already in use"
          PORT=""
        fi
      else
        PORT="$(find_free_port)"
      fi

      if [[ -n "$PORT" ]]; then
        printf '\n[run] selected Playwright server on http://127.0.0.1:%s\n' "$PORT"
        (
          cd "$WEB_DIR" &&
            npx next start --hostname 127.0.0.1 --port "$PORT"
        ) &
        SERVER_PID=$!

        if wait_for_url "http://127.0.0.1:$PORT"; then
          (
            cd "$WEB_DIR" &&
              PLAYWRIGHT_BASE_URL="http://127.0.0.1:$PORT" \
              PLAYWRIGHT_SKIP_WEBSERVER=1 \
              PLAYWRIGHT_OUTPUT_DIR="test-results/release-regression" \
              npx playwright test --config=playwright.config.ts "${PLAYWRIGHT_SPECS[@]}"
          )
          playwright_status=$?
          if [[ $playwright_status -eq 0 ]]; then
            record_pass "selected Playwright"
          else
            record_fail "selected Playwright" "exit $playwright_status"
          fi
        else
          record_fail "selected Playwright" "next start did not become ready on port $PORT"
        fi
      fi
    fi
  fi
fi

if ! has_command python3; then
  record_skip "backend smoke" "python3 is required"
elif ! python3 -m pytest --version >/dev/null 2>&1; then
  record_skip "backend smoke" "pytest is not installed for python3"
else
  (
    cd "$ROOT_DIR" &&
      python3 -m pytest "${BACKEND_SMOKE_TESTS[@]}"
  )
  backend_status=$?
  if [[ $backend_status -eq 0 ]]; then
    record_pass "backend smoke"
  else
    record_fail "backend smoke" "exit $backend_status"
  fi
fi

printf '\nRelease regression summary\n'
printf 'Passed: %s\n' "${#PASSED[@]}"
if [[ ${#PASSED[@]} -gt 0 ]]; then
  for item in "${PASSED[@]}"; do
    printf '  PASS %s\n' "$item"
  done
fi
printf 'Skipped: %s\n' "${#SKIPPED[@]}"
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  for item in "${SKIPPED[@]}"; do
    printf '  SKIP %s\n' "$item"
  done
fi
printf 'Failed: %s\n' "${#FAILED[@]}"
if [[ ${#FAILED[@]} -gt 0 ]]; then
  for item in "${FAILED[@]}"; do
    printf '  FAIL %s\n' "$item"
  done
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  exit 1
fi
