#!/usr/bin/env sh

# Shared startup guard. Never repair ownership or permissions automatically.
set -eu

for runtime_dir in "${PERFORMANCE_AI_STORAGE_DIR:-/data}" "${MPLCONFIGDIR:-/tmp/mplconfig}"; do
  if ! mkdir -p "$runtime_dir" || [ ! -w "$runtime_dir" ] || [ ! -x "$runtime_dir" ]; then
    printf '%s\n' "Civora startup blocked: runtime directory $runtime_dir must be writable and searchable by the service user. Container volumes must grant UID/GID 10001 access." >&2
    exit 1
  fi
done
