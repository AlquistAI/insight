#!/usr/bin/env bash
set -o errexit

# Here you can run any operations needed before server start (e.g. migrations)
# ...

# Start Uvicorn
exec /usr/local/bin/uvicorn \
  --host "0.0.0.0" \
  --port "${ALCHEMIST_CONTAINER_PORT:-9642}" \
  --log-level "${ALCHEMIST_LOG_LEVEL:-debug}" \
  run:fast_app
