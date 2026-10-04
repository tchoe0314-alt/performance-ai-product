#!/usr/bin/env sh

set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$script_dir/check_backend_storage.sh"

# Preserve the alternate image's single-process Uvicorn startup and default port.
exec python -m uvicorn backend.api.app:app --host 0.0.0.0 --port "${PORT:-8080}"
