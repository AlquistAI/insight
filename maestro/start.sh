#!/usr/bin/env bash
set -o errexit

# Here you can run any operations needed before server start (e.g. migrations)
# ...

# Start Uvicorn
exec /usr/local/bin/uvicorn \
  --host "0.0.0.0" \
  --port "${MAESTRO_CONTAINER_PORT:-8020}" \
  --log-level "${MAESTRO_LOG_LEVEL:-debug}" \
  run:fast_app
